"""Preserve RelicDataInfo stories from the verified official Korean game pack.

String keys bind through XXH64 seed 0, UTF-8. ItemBGDesc hash fields in
ItemConfigRelic independently check every binding. Original site documents and
game inputs are read-only; this generator writes only the requested JSON.
"""
import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

from build_official_universe_texts import official_input, corpus_digest

SITE = Path(__file__).resolve().parents[1]
TABLES = ("RelicDataInfo", "RelicConfig", "ItemConfigRelic", "RelicSetConfig")
FIELDS = ("RelicName", "ItemBGDesc", "BGStoryTitle", "BGStoryContent")
MASK = (1 << 64) - 1
PRIMES = (0x9E3779B185EBCA87, 0xC2B2AE3D27D4EB4F,
          0x165667B19E3779F9, 0x85EBCA77C2B2AE63, 0x27D4EB2F165667C5)


def xxh64(data):
    """Standard XXH64, seed 0; no game secrets or guessed hash seeds."""
    a, b, c, d, e = PRIMES
    def rotate(n, bits):
        n &= MASK
        return ((n << bits) | (n >> (64 - bits))) & MASK
    def lane(acc, value):
        return rotate(acc + value * b, 31) * a & MASK
    pos = 0
    if len(data) >= 32:
        states = [(a + b) & MASK, b, 0, (-a) & MASK]
        while pos + 32 <= len(data):
            for i in range(4):
                states[i] = lane(states[i], int.from_bytes(data[pos+i*8:pos+i*8+8], "little"))
            pos += 32
        result = sum(rotate(n, bits) for n, bits in zip(states, (1, 7, 12, 18))) & MASK
        for n in states:
            result = ((result ^ lane(0, n)) * a + d) & MASK
    else:
        result = e
    result = (result + len(data)) & MASK
    while pos + 8 <= len(data):
        value = int.from_bytes(data[pos:pos+8], "little")
        result = (rotate(result ^ lane(0, value), 27) * a + d) & MASK
        pos += 8
    if pos + 4 <= len(data):
        result = (rotate(result ^ (int.from_bytes(data[pos:pos+4], "little") * a), 23) * b + c) & MASK
        pos += 4
    for value in data[pos:]:
        result = rotate(result ^ (value * e), 11) * a & MASK
    result ^= result >> 33
    result = result * b & MASK
    result ^= result >> 29
    result = result * c & MASK
    return result ^ (result >> 32)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(root, archive, skill, output):
    for raw, expected in [(b"", 0xef46db3751d8e999), (b"a", 0xd24ec4f1a98c6e5b), (b"abc", 0x44bc2cf5ad770999)]:
        assert xxh64(raw) == expected
    before = corpus_digest()
    texts, evidence, readable = official_input(root, skill)
    bound = json.loads((SITE / "data/official-universe-texts.json").read_text("utf8"))["evidence"]
    assert evidence["entry"] == bound["entry"]
    assert evidence["koreanPack"] == bound["koreanPack"]
    assert sha(archive.read_bytes()) == bound["archiveSha256"]
    metadata, hashes = {}, {}
    wanted = {"ExcelOutput/" + name + ".json" for name in TABLES}
    with tarfile.open(archive, "r:gz") as source:
        for member in source:
            name = member.name.split("/", 1)[-1]
            if name in wanted:
                assert name not in metadata
                raw = source.extractfile(member).read()
                metadata[name] = json.loads(raw)
                hashes[name] = sha(raw)
    assert set(metadata) == wanted
    info = metadata["ExcelOutput/RelicDataInfo.json"]
    configs = metadata["ExcelOutput/RelicConfig.json"]
    item_rows = metadata["ExcelOutput/ItemConfigRelic.json"]
    items = {r["ID"]: (i, r) for i, r in enumerate(item_rows)}
    assert len(items) == len(item_rows)
    preserved = {}
    for document in json.loads((SITE / "data/catalog.json").read_text("utf8")):
        if document["category"] != "유물 이야기":
            continue
        path = SITE / "data/documents" / (document["id"] + ".json")
        original = json.loads(path.read_text("utf8"))
        match = re.fullmatch(r"ItemConfigRelic:(\d+)", original["source"])
        assert match
        preserved[int(match[1])] = {"id": document["id"], "sha256": sha(path.read_bytes()), "title": original["title"]}
    records, unresolved, observed, mapped, checks = [], [], set(), set(), 0
    for index, row in enumerate(info):
        key = (row["SetID"], row["Type"])
        assert key not in observed
        observed.add(key)
        fields = {}
        for field in FIELDS:
            string_key = row[field]
            assert isinstance(string_key, str) and string_key
            text_hash = str(xxh64(string_key.encode("utf8")))
            if text_hash not in texts:
                unresolved.append({"sourceRowIndex": index, "setId": row["SetID"], "type": row["Type"],
                                   "fieldKey": field, "stringKey": string_key, "hash": text_hash,
                                   "status": "NO_OFFICIAL_KOREAN_HASH_JOIN"})
                continue
            source = texts[text_hash]
            fields[field] = {"fieldKey": field, "stringKey": string_key, "hash": text_hash,
                             "raw": source["raw"], "text": readable(source["raw"]),
                             "legacy": str(source["legacy"]), "offset": source["offset"],
                             "end": source["end"], "hasParams": source["has_params"],
                             "sourcePointer": f"/{index}/{field}"}
        # The explicit ItemConfigRelic hash validates the string-key algorithm,
        # including story rows without an existing site document.
        item_proofs, related, related_proofs = [], [], []
        for ci, config in enumerate(configs):
            if (config["SetID"], config["Type"]) != key:
                continue
            ii, item = items[config["ID"]]
            desc_hash = str(item["ItemBGDesc"]["Hash"])
            assert desc_hash == str(xxh64(row["ItemBGDesc"].encode("utf8")))
            checks += 1
            proof = {"itemId": config["ID"], "relicConfigPointer": f"/{ci}",
                     "itemConfigPointer": f"/{ii}/ItemBGDesc", "hash": desc_hash}
            item_proofs.append(proof)
            original = preserved.get(config["ID"])
            if original:
                assert "RelicName" in fields and original["title"] == fields["RelicName"]["text"]
                related.append(original["id"])
                related_proofs.append({**proof, "documentId": original["id"], "documentSha256": original["sha256"]})
                mapped.add(original["id"])
        assert item_proofs, key
        if "BGStoryContent" not in fields:
            continue
        story = fields["BGStoryContent"]
        records.append({"id": f"relic-background-{row['SetID']}-{row['Type'].lower()}",
                        "title": fields.get("RelicName", {}).get("text", "유물 기록"),
                        "storyTitle": fields.get("BGStoryTitle", {}).get("text", ""),
                        "text": story["text"], "raw": story["raw"], "hash": story["hash"],
                        "sourceRowId": {"setId": row["SetID"], "type": row["Type"]},
                        "sourceRowIndex": index,
                        "source": {"table": "ExcelOutput/RelicDataInfo.json", "pointer": story["sourcePointer"],
                                   "stringKey": story["stringKey"], "sha256": hashes["ExcelOutput/RelicDataInfo.json"]},
                        "relatedItemIds": related, "relatedItemMappings": related_proofs,
                        "itemDescriptionHashBindings": item_proofs, "fields": fields})
    assert mapped == {d["id"] for d in preserved.values()}, "Preserved relic document lost its exact story binding"
    collections = []
    for index, row in enumerate(metadata["ExcelOutput/RelicSetConfig.json"]):
        selected = [r["id"] for r in records if r["sourceRowId"]["setId"] == row["SetID"]]
        if not selected:
            continue
        name_hash = str(row["SetName"]["Hash"])
        if name_hash not in texts:
            unresolved.append({"sourceTable": "ExcelOutput/RelicSetConfig.json", "sourceRowIndex": index,
                               "setId": row["SetID"], "fieldKey": "SetName", "hash": name_hash,
                               "status": "NO_OFFICIAL_KOREAN_HASH_JOIN"})
            continue
        source = texts[name_hash]
        collections.append({"id": "relic-set-" + str(row["SetID"]), "setId": row["SetID"],
                            "name": readable(source["raw"]), "recordIds": selected,
                            "field": {"fieldKey": "SetName", "hash": name_hash, "raw": source["raw"],
                                      "text": readable(source["raw"]), "legacy": str(source["legacy"]),
                                      "offset": source["offset"], "end": source["end"], "hasParams": source["has_params"],
                                      "sourcePointer": f"/{index}/SetName"},
                            "sourceTable": "ExcelOutput/RelicSetConfig.json", "sourceRowIndex": index})
    assert corpus_digest() == before
    result = {"schema": "starrail-relic-backgrounds.v1", "records": records, "collections": collections, "unresolved": unresolved,
              "evidence": {**evidence, "sourceStatus": "OFFICIAL_PATCH_KOREAN_TEXTMAP", "installedClientReverified": False,
                           "metadataCommit": bound["metadataCommit"], "archiveSha256": bound["archiveSha256"],
                           "metadataFiles": hashes, "stringKeyHash": "XXH64 seed0 UTF-8",
                           "stringKeyBindingChecks": checks, "preservedCorpus": before},
              "counts": {"sourceRows": len(info), "records": len(records), "fields": sum(len(r["fields"]) for r in records),
                         "linkedPreservedDocuments": len(mapped), "unlinkedRecords": sum(not r["relatedItemIds"] for r in records),
                         "collections": len(collections), "collectionFields": len(collections), "unresolvedFields": len(unresolved)}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), "utf8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--skill", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=SITE / "data/relic-backgrounds.json")
    args = parser.parse_args()
    build(args.official_root, args.archive, args.skill, args.output)
