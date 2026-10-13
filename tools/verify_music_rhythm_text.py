"""Read-only replay of the pinned MusicRhythm screen-text consumer profile.

No producer imports or game-code execution. Configuration/installation edition
alignment and runtime display are intentionally unverified.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct

PIN = 'e2a4d9d46dfa668494508f6dad6833607e622345b1cb56ee6137ae835d16b130'

def require(value, message):
    if not value:
        raise ValueError(message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def profile_check(profile):
    require(profile['schema'] == 'starrail-music-rhythm-text-domain.v1'
            and profile['role'] == 'SCREEN_TEXT'
            and profile['callerSourceKind'] == 'PUBLIC_JSON_CONFIGURATION_NATIVE_CONSUMER_BOUND'
            and profile['installedConfigEditionMatch'] is None
            and profile['runtimeDisplayConfirmed'] is False, 'Screen domain or edition claim differs')
    fields = {(t['class'], f['name']): f for t in profile['types'] for f in t['fields']}
    for key, offset in ((('RPG.GameCore.NoteGroupConfig','AutoBubble'),24),
                        (('RPG.GameCore.AutoBubbleConfig','HitTextId'),32),
                        (('RPG.GameCore.AutoBubbleConfig','MissTextId'),36),
                        (('RPG.GameCore.BubbleNotifyConfig','BubbleId'),20),
                        (('RPG.GameCore.NoteNotifyConfig','BubbleConfig'),56),
                        (('RPG.Client.MusicRhythmBubbleInfo','TextId'),36)):
        require(fields[key]['runtimeFieldOffset'] == offset, 'Typed native field offset differs')
    require(fields[('RPG.GameCore.NoteNotifyType','Bubble')]['primitiveIntegerDefault']['integer'] == 2,
            'Native Bubble enum domain differs')
    for function in profile['functions']:
        raw = bytes.fromhex(function['raw'])
        require(len(raw) == function['bytes'] and sha(raw) == function['sha256'], 'Native function raw/hash differs')
        if 'instructions' in function:
            pos = int(function['va'],16)
            for instruction in function['instructions']:
                encoded = bytes.fromhex(instruction['bytes'])
                require(int(instruction['va'],16) == pos
                        and raw[pos-int(function['va'],16):pos-int(function['va'],16)+len(encoded)] == encoded,
                        'Whole native instruction coverage differs')
                pos += len(encoded)
            require(pos-int(function['va'],16) == len(raw), 'Native instruction EOF differs')
        else:
            pos = function['codeBytes']
            for table in function['switchTables']:
                encoded = bytes.fromhex(table['raw'])
                require(int(table['tableVA'],16)-int(function['va'],16) == pos
                        and len(encoded) == 4*table['entries'] and raw[pos:pos+len(encoded)] == encoded,
                        'Inline switch table coverage differs')
                targets = [hex(int(table['tableVA'],16)+n[0]) for n in struct.iter_unpack('<i',encoded)]
                require(targets == table['targets'] and all(0 <= int(v,16)-int(function['va'],16) < function['codeBytes'] for v in targets),
                        'Inline switch target domain differs')
                pos += len(encoded)
            require(pos == len(raw) and function['switchTables'][0]['targets'][2] == '0x18c308fa8',
                    'Bubble enum switch target or function EOF differs')
    require(profile['parameters'][0]['parameters'][2]['class'] == 'RPG.GameCore.NoteGroupConfig', 'Native constructor parameter differs')
    require(profile['talkTable']['method']['nativePointerVA'] == 0x19db56cf0, 'TalkSentence GetData domain differs')
    calls = profile['lua']['calls']
    require([c['pc'] for c in calls] == [79,90]
            and calls[0]['arguments'] == [['member',['parameter',1],'TextId']]
            and calls[1]['arguments'][-1][-1] == 'TalkSentenceText', 'Installed Lua screen consumer differs')
    require(len(profile['configurationSources']) == 20, 'Configuration source cohort differs')

def source_replay(profile, game_root):
    inputs = {'GameAssembly.dll':game_root/'GameAssembly.dll'}
    for name in ('global-metadata.dat','startup-metadata.dat'):
        inputs[name] = game_root/'StarRail_Data/il2cpp_data/Metadata'/name
    for entry in profile['nativeInputs']:
        path = inputs[entry['name']]
        require(path.stat().st_size == entry['bytes'], 'Current native input size differs')
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(8*1024*1024),b''):
                h.update(chunk)
        require(h.hexdigest() == entry['sha256'], 'Current native input hash differs')
    count = 0
    def span(name, offset, raw):
        nonlocal count
        expected = bytes.fromhex(raw)
        with inputs[name].open('rb') as stream:
            stream.seek(offset)
            require(stream.read(len(expected)) == expected, 'Current native metadata/function span differs')
        count += 1
    for function in profile['functions']:
        span('GameAssembly.dll',function['fileOffset'],function['raw'])
    for record in profile['types']:
        span('global-metadata.dat',record['metadataFileOffset'],record['metadataRaw'])
        for field in record['fields']:
            span('global-metadata.dat',field['metadataFileOffset'],field['metadataRaw'])
            span('GameAssembly.dll',field['typeRecordFileOffset'],field['typeRecordRaw'])
            span('global-metadata.dat',field['runtimeFieldOffsetFile'],field['runtimeFieldOffsetRaw'])
            default = field.get('primitiveIntegerDefault')
            if default:
                span('global-metadata.dat',default['entryFileOffset'],default['entryRaw'])
                span('global-metadata.dat',default['dataFileOffset'],default['dataRaw'])
    method = profile['talkTable']['method']
    span('global-metadata.dat',method['metadataFileOffset'],method['metadataRaw'])
    span('GameAssembly.dll',method['nativeFileOffset'],method['nativeFirst64'])
    for method in profile['parameters']:
        for parameter in method['parameters']:
            span('global-metadata.dat',parameter['metadataOffset'],parameter['raw'])
            span('GameAssembly.dll',parameter['typeOffset'],parameter['typeRaw'])
    lua = profile['lua']; source = lua['source']
    matches = list((game_root/'StarRail_Data/StreamingAssets').rglob(source['file']))
    require(len(matches) == 1, 'Installed Lua pack absent/ambiguous')
    with matches[0].open('rb') as stream:
        stream.seek(source['entryOffset']); raw = stream.read(source['entryLength'])
    require(len(raw) == lua['bytes'] and sha(raw) == lua['entrySha256']
            and hashlib.md5(raw).hexdigest() == source['entryMd5'], 'Installed Lua entry binding differs')
    for call in lua['calls']:
        require(0 <= call['start'] < call['end'] <= len(raw) and call['end']-call['start'] == 4, 'Lua CALL span bounds differ')
    return {'actualNativeInputHashes':len(inputs),'actualNativeSpans':count,'actualInstalledLuaEntries':1}

def self_test(profile):
    cases = []
    def reject(name, mutate):
        value = copy.deepcopy(profile); mutate(value)
        try:profile_check(value)
        except (ValueError,KeyError,IndexError):cases.append(name);return
        raise ValueError('Negative accepted: '+name)
    reject('voice role substituted',lambda d:d.update(role='SPOKEN'))
    reject('installation edition asserted',lambda d:d.update(installedConfigEditionMatch=True))
    reject('runtime display asserted',lambda d:d.update(runtimeDisplayConfirmed=True))
    reject('native constructor parameter substituted',lambda d:d['parameters'][0]['parameters'][2].update({'class':'VoiceConfig'}))
    reject('Lua TextId argument substituted',lambda d:d['lua']['calls'][0].update({'arguments':[['member',['parameter',1],'VoiceId']]}))
    reject('switch Bubble domain substituted',lambda d:d['functions'][2]['switchTables'][0]['targets'].__setitem__(2,'0x18c308f70'))
    return cases

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--game-root',type=Path)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--report',type=Path)
    args = parser.parse_args(); raw = (args.repo/'tools/music_rhythm_text_proof.json').read_bytes()
    require(sha(raw) == PIN, 'Closed native consumer profile differs')
    profile = json.loads(raw); profile_check(profile)
    counts = source_replay(profile,args.game_root) if args.game_root else {}
    report = {'status':'PASS','schema':'starrail-music-rhythm-independent-profile-verification.v1',
              'profileSha256':PIN,'counts':counts,'negativeSelfTests':self_test(profile) if args.self_test else [],
              'limits':['Lua consumer semantics are bound to the pinned analysis by the exact installed module hash; game code is not executed.',
                        'Public configuration uses and rendered screen roles are independently checked by verify_dialogue_contexts.py.',
                        'Configuration/installation edition alignment and runtime display remain unverified.']}
    if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
