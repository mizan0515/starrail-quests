"""Declared alternative-voice configuration references; no speech inference."""
import hashlib
import json
from pathlib import Path

PROOF_PATH = Path(__file__).with_name('multivoice_config_proof.json')
_proof_bytes = PROOF_PATH.read_bytes()
if hashlib.sha256(_proof_bytes).hexdigest() != '89dc023034b910688aed3d7d24749975fa6ba965ed8c3dcf83fc6e0e33325e69':
    raise ValueError('Alternative-voice native domain proof changed')
PROOF = json.loads(_proof_bytes)
SOURCE = 'ExcelOutput/TalkSentenceMultiVoice.json'
KIND = 'MULTIVOICE_CONFIG_TALK_SENTENCE_ID'


def configuration_row(row):
    return (isinstance(row, dict) and set(row) == {'TalkSentenceID', 'VoiceIDList'}
            and type(row['TalkSentenceID']) is int and 0 < row['TalkSentenceID'] < 2**32
            and isinstance(row['VoiceIDList'], list) and bool(row['VoiceIDList'])
            and all(type(value) is int and 0 < value < 2**32 for value in row['VoiceIDList']))


def references(row, path, pointer):
    if path == SOURCE and pointer.startswith('/') and pointer[1:].isdigit() and configuration_row(row):
        yield row['TalkSentenceID'], pointer + '/TalkSentenceID', KIND


def source_record(row, pointer):
    if not configuration_row(row):
        raise ValueError('Unsupported alternative-voice configuration row')
    return {'sourceRole': PROOF['role'],
            'recordContext': {'pointer': pointer, 'fields': row,
                              'serialized': json.dumps(row, ensure_ascii=False, indent=2)},
            'configurationReference': {'field': 'TalkSentenceID', 'voiceField': 'VoiceIDList',
                                       'proofSchema': PROOF['schema'],
                                       'proofSha256': hashlib.sha256(_proof_bytes).hexdigest()}}
