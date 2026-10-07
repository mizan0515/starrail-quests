"""Read-only DesignV v4 and observed HSR table serialization. Stdlib only."""
from pathlib import Path
import json, struct, hashlib

def varint(data, pos):
    number = 0
    for shift in range(0, 77, 7):
        if pos >= len(data): raise ValueError('Truncated varint')
        byte = data[pos]; pos += 1; number |= (byte & 127) << shift
        if byte < 128: return number, pos
    raise ValueError('Varint exceeds supported width')

def signed(number): return (number >> 1) ^ -(number & 1)

def read_catalog(data):
    magic, version, count, entry_count = struct.unpack_from('>IIII', data)
    if (magic, version) != (255, 4): raise ValueError(f'Unsupported DesignV header: {magic}, {version}')
    pos = 16; files = []; total = 0
    for _ in range(count):
        name = int.from_bytes(data[pos:pos+8], 'big'); pos += 8
        md5 = data[pos:pos+16].hex(); pos += 16
        size, n = struct.unpack_from('>QI', data, pos); pos += 12; entries = []; end = 0
        for _ in range(n):
            key, length, offset = struct.unpack_from('>QII', data, pos); pos += 16
            if offset != end: raise ValueError('Non-contiguous DesignV entry offsets')
            end = offset + length; entries.append((key, length, offset))
        language_length = struct.unpack_from('>H', data, pos)[0]; pos += 2
        language = data[pos:pos+language_length].decode('ascii'); pos += language_length
        flag = data[pos]; pos += 1
        if end != size: raise ValueError('DesignV file size mismatch')
        files.append(dict(name=name, file=md5+'.bytes', size=size, language=language, flag=flag, entries=entries)); total += n
    if pos != len(data) or total != entry_count: raise ValueError('DesignV trailing bytes / entry count mismatch')
    return files

class LocalData:
    def __init__(self, root):
        self.root = Path(root).resolve(); self.files = {}; self.evidence = {}
        m = self.root/'Persistent/DesignData/Windows/M_DesignV.bytes'
        if not m.exists(): m = self.root/'StreamingAssets/DesignData/Windows/M_DesignV.bytes'
        manifest = self.read(m)
        if manifest.startswith(b'SRMI'):
            if len(manifest)!=66:raise ValueError('Unsupported SRMI manifest length')
            digest=b''.join(manifest[i:i+4][::-1] for i in range(28,44,4)).hex()
            meta={'format':'SRMI','ContentHash':digest,'FileSize':int.from_bytes(manifest[44:52],'little'),'raw_hex':manifest.hex()}
        else:meta = json.loads(manifest.decode('utf-8-sig'))
        self.version = meta
        p = m.parent/('DesignV_'+meta['ContentHash']+'.bytes')
        self.catalog = read_catalog(self.read(p))
        self.entries = {key: (f, length, offset) for f in self.catalog for key,length,offset in f['entries']}

    def read(self, path):
        path = Path(path).resolve()
        if path not in self.files:
            raw = path.read_bytes(); self.files[path] = raw
            self.evidence[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
        return self.files[path]

    def file_path(self, info):
        for base in ('Persistent','StreamingAssets'):
            p = self.root/base/'DesignData/Windows'
            if info['language']: p = p/info['language']
            p = p/info['file']
            if p.exists(): return p
        raise FileNotFoundError('Local design file unavailable: '+info['file'])

    def entry(self, key):
        info,length,offset = self.entries[int(key)]; p = self.file_path(info); data = self.read(p)
        if len(data) != info['size']: raise ValueError('Local file / catalog size mismatch')
        return data[offset:offset+length], {'file':str(p), 'entry_hash':str(key), 'offset':offset, 'size':length}

    def verify_unchanged(self):
        for path, evidence in self.evidence.items():
            h=hashlib.sha256()
            with open(path,'rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024),b''): h.update(chunk)
            if h.hexdigest()!=evidence['sha256']: raise ValueError('Source changed during extraction: '+path)

def decode_table(data, schema):
    pos = int(data[0] == 0); count,pos = varint(data,pos); count = signed(count)
    if not 0 <= count <= 2000000: raise ValueError('Invalid table count')
    def value(kind):
        nonlocal pos
        if kind=='hash':
            legacy,pos=varint(data,pos); number,pos=varint(data,pos)
            return {'Hash':number,'Legacy':legacy}
        if kind=='str':
            n,pos=varint(data,pos)
            if pos+n > len(data): raise ValueError('Truncated string')
            text=data[pos:pos+n].decode('utf8');pos+=n;return text
        if kind=='float':
            number=struct.unpack_from('<f',data,pos)[0];pos+=4;return number
        if isinstance(kind,list):
            n,pos=varint(data,pos);n=signed(n)
            if not 0<=n<=2000000:raise ValueError('Invalid array count')
            return [value(kind[0]) for _ in range(n)]
        if isinstance(kind,dict):return object_row(list(kind.items()))
        number,pos=varint(data,pos)
        return signed(number) if kind=='enum' else number
    def object_row(fields):
        nonlocal pos
        flags,pos=varint(data,pos)
        if flags>>len(fields):raise ValueError('Schema has unknown active field slots')
        return {key:value(kind) for i,(key,kind) in enumerate(fields) if flags&(1<<i)}
    rows=[]
    for _ in range(count):
        start=pos; row=object_row(schema); row['_offset']=start; row['_end']=pos;rows.append(row)
    if pos!=len(data):raise ValueError(f'Table end mismatch: {pos} / {len(data)}')
    return rows

def decode_textmap(data):
    pos=0;count,pos=varint(data,pos);count=signed(count);rows=[]
    for _ in range(count):
        start=pos;flags,pos=varint(data,pos)
        if flags&~7:raise ValueError('Unsupported Korean TextMap fields')
        legacy=key=0;text='';params=0
        if flags&1:legacy,pos=varint(data,pos);key,pos=varint(data,pos)
        if flags&2:
            n,pos=varint(data,pos)
            if pos+n>len(data):raise ValueError('Truncated Korean text')
            text=data[pos:pos+n].decode('utf8');pos+=n
        if flags&4:params,pos=varint(data,pos)
        rows.append(dict(legacy=legacy,hash=key,raw=text,has_params=params,offset=start,end=pos))
    if pos!=len(data):raise ValueError('Korean TextMap end mismatch')
    if len({r['hash'] for r in rows})!=len(rows):raise ValueError('Duplicate TextMap hash')
    return rows
