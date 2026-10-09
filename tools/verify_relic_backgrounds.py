"""Independently verify story coverage, original bytes and exact item bindings."""
import argparse
import copy
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path

from build_relic_backgrounds import xxh64

SITE = Path(__file__).resolve().parents[1]
FIELDS = {"RelicName", "ItemBGDesc", "BGStoryTitle", "BGStoryContent"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def readable(raw):
    text = raw.replace("\\n", "\n").replace("\u00a0", " ")
    text = re.sub(r"\{RUBY_B#[^}]*\}|\{RUBY_E#[^}]*\}", "", text)
    text = re.sub(r"</?(?:color|size|b|i|u|align|voffset|indent|line-height|unbreak)(?:=[^>]*)?>", "", text, flags=re.I)
    return re.sub(r"<br\s*/?>", "\n", text, flags=re.I)


def corpus():
    result, count = hashlib.sha256(), 0
    for folder in ("documents", "dialogues"):
        for path in sorted((SITE / "data" / folder).glob("*.json")):
            result.update((path.relative_to(SITE).as_posix() + "\0" + digest(path.read_bytes()) + "\n").encode())
            count += 1
    return {"files": count, "sha256": result.hexdigest()}


def public_safe(value):
    if isinstance(value, dict):
        for item in value.values():
            public_safe(item)
    elif isinstance(value, list):
        for item in value:
            public_safe(item)
    elif isinstance(value, str):
        assert not re.search(r"(?:^[A-Za-z]:[\\/]|^\\\\|\.codex-work|dispatch_seed)", value)


def check_field(field, index, key, entry):
    assert field["fieldKey"] == key
    assert field["sourcePointer"] == f"/{index}/{key}"
    assert field["hash"] == str(xxh64(field["stringKey"].encode("utf8")))
    assert field["text"] == readable(field["raw"])
    assert 0 <= field["offset"] < field["end"] <= entry["length"]
    assert isinstance(field["legacy"], str) and isinstance(field["hash"], str)


def main(args):
    original_bytes = args.input.read_bytes()
    data = json.loads(original_bytes)
    public_safe(data)
    assert data["schema"] == "starrail-relic-backgrounds.v1"
    evidence = data["evidence"]
    universe = json.loads((SITE / "data/official-universe-texts.json").read_text("utf8"))["evidence"]
    for key in ("clientVersion", "officialHost", "manifestSha256", "catalogSha256", "catalogFile", "koreanPack", "entry", "archiveSha256", "metadataCommit"):
        assert evidence[key] == universe[key], key
    assert evidence["stringKeyHash"] == "XXH64 seed0 UTF-8"
    assert corpus() == evidence["preservedCorpus"]
    ids, coordinates, linked, fields = set(), set(), set(), 0
    for record in data["records"]:
        row_id, index = record["sourceRowId"], record["sourceRowIndex"]
        assert record["id"] == f"relic-background-{row_id['setId']}-{row_id['type'].lower()}"
        assert record["id"] not in ids and index not in coordinates
        ids.add(record["id"])
        coordinates.add(index)
        assert set(record["fields"]) <= FIELDS and "BGStoryContent" in record["fields"]
        for key, field in record["fields"].items():
            check_field(field, index, key, evidence["entry"])
            fields += 1
        story = record["fields"]["BGStoryContent"]
        assert (record["text"], record["raw"], record["hash"]) == (story["text"], story["raw"], story["hash"])
        assert record["title"] == record["fields"]["RelicName"]["text"]
        assert record["storyTitle"] == record["fields"].get("BGStoryTitle", {}).get("text", "")
        assert record["source"] == {"table": "ExcelOutput/RelicDataInfo.json", "pointer": story["sourcePointer"],
                                   "stringKey": story["stringKey"], "sha256": evidence["metadataFiles"]["ExcelOutput/RelicDataInfo.json"]}
        assert record["relatedItemIds"] == [p["documentId"] for p in record["relatedItemMappings"]]
        for proof in record["relatedItemMappings"]:
            path = SITE / "data/documents" / (proof["documentId"] + ".json")
            assert digest(path.read_bytes()) == proof["documentSha256"]
            doc = json.loads(path.read_text("utf8"))
            assert doc["source"] == "ItemConfigRelic:" + str(proof["itemId"])
            assert doc["category"] == "유물 이야기" and doc["title"] == record["title"]
            assert any(r["source"].endswith(".ItemBGDesc") and r["hash"] == proof["hash"] and r["text"] == record["fields"]["ItemBGDesc"]["text"]
                       for section in doc["sections"] for r in section["rows"])
            linked.add(doc["id"])
    preserved = {r["id"] for r in json.loads((SITE / "data/catalog.json").read_text("utf8")) if r["category"] == "유물 이야기"}
    assert linked == preserved
    assert {r for c in data["collections"] for r in c["recordIds"]} == ids
    assert len({c["setId"] for c in data["collections"]}) == len(data["collections"])
    for collection in data["collections"]:
        field = collection["field"]
        assert collection["id"] == "relic-set-" + str(collection["setId"])
        assert collection["name"] == field["text"] == readable(field["raw"])
        assert field["sourcePointer"] == f"/{collection['sourceRowIndex']}/SetName"
        assert collection["recordIds"] == [r["id"] for r in data["records"] if r["sourceRowId"]["setId"] == collection["setId"]]
    expected_counts = {"sourceRows": data["counts"]["sourceRows"], "records": len(ids), "fields": fields,
                       "linkedPreservedDocuments": len(linked), "unlinkedRecords": sum(not r["relatedItemIds"] for r in data["records"]),
                       "collections": len(data["collections"]), "collectionFields": len(data["collections"]),
                       "unresolvedFields": len(data["unresolved"])}
    assert data["counts"] == expected_counts
    sample = data["records"][0]["fields"]["BGStoryContent"]
    for key, value in [("raw", sample["raw"] + "x"), ("hash", str(int(sample["hash"]) + 1)), ("sourcePointer", "/0/ItemBGDesc")]:
        changed = copy.deepcopy(sample)
        changed[key] = value
        try:
            check_field(changed, data["records"][0]["sourceRowIndex"], "BGStoryContent", evidence["entry"])
        except AssertionError:
            pass
        else:
            raise AssertionError("Accepted mutation: " + key)
    deep = bool(args.archive or args.official_root or args.skill)
    if deep:
        assert args.archive and args.official_root and args.skill
        assert digest(args.archive.read_bytes()) == evidence["archiveSha256"]
        metadata = {}
        with tarfile.open(args.archive, "r:gz") as source:
            for member in source:
                name = member.name.split("/", 1)[-1]
                if name in evidence["metadataFiles"]:
                    raw = source.extractfile(member).read()
                    assert digest(raw) == evidence["metadataFiles"][name]
                    metadata[name] = json.loads(raw)
        assert set(metadata) == set(evidence["metadataFiles"])
        sys.path.insert(0, str(args.skill / "scripts"))
        from binary import read_catalog, decode_textmap
        root = args.official_root
        manifest = (root / "M_DesignV.bytes").read_bytes()
        assert digest(manifest) == evidence["manifestSha256"]
        catalog_raw = (root / evidence["catalogFile"]).read_bytes()
        assert digest(catalog_raw) == evidence["catalogSha256"]
        kr = next(r for r in read_catalog(catalog_raw) if r["language"] == "kr")
        pack = (root / "kr" / kr["file"]).read_bytes()
        assert digest(pack) == evidence["koreanPack"]["sha256"] and hashlib.md5(pack).hexdigest() == evidence["koreanPack"]["md5"]
        key, length, offset = next(r for r in kr["entries"] if str(r[0]) == evidence["entry"]["key"])
        assert (length, offset) == (evidence["entry"]["length"], evidence["entry"]["offset"])
        raw_entry = pack[offset:offset+length]
        assert digest(raw_entry) == evidence["entry"]["sha256"]
        original_rows = decode_textmap(raw_entry)
        assert len(original_rows) == evidence["entry"]["rows"]
        texts = {str(r["hash"]): r for r in original_rows}
        info = metadata["ExcelOutput/RelicDataInfo.json"]
        assert len(info) == data["counts"]["sourceRows"]
        expected_records, missing = set(), set()
        for i, row in enumerate(info):
            for field in FIELDS:
                hash_value = str(xxh64(row[field].encode("utf8")))
                if hash_value not in texts:
                    missing.add((i, field, hash_value))
                elif field == "BGStoryContent":
                    expected_records.add(i)
        assert coordinates == expected_records
        story_missing = {x for x in missing}
        collection_missing = set()
        for i, row in enumerate(metadata["ExcelOutput/RelicSetConfig.json"]):
            if row["SetID"] in {r["sourceRowId"]["setId"] for r in data["records"]} and str(row["SetName"]["Hash"]) not in texts:
                collection_missing.add((i, "SetName", str(row["SetName"]["Hash"])))
        assert {(u["sourceRowIndex"], u["fieldKey"], u["hash"]) for u in data["unresolved"]} == story_missing | collection_missing
        for collection in data["collections"]:
            source = metadata["ExcelOutput/RelicSetConfig.json"][collection["sourceRowIndex"]]
            field = collection["field"]
            assert source["SetID"] == collection["setId"] and str(source["SetName"]["Hash"]) == field["hash"]
            original = texts[field["hash"]]
            for public, key in [("raw", "raw"), ("offset", "offset"), ("end", "end"), ("hasParams", "has_params")]:
                assert field[public] == original[key]
            assert field["legacy"] == str(original["legacy"])
        configs = metadata["ExcelOutput/RelicConfig.json"]
        items = metadata["ExcelOutput/ItemConfigRelic.json"]
        binding_count = 0
        for record in data["records"]:
            index = record["sourceRowIndex"]
            row = info[index]
            assert record["sourceRowId"] == {"setId": row["SetID"], "type": row["Type"]}
            for field, value in record["fields"].items():
                assert row[field] == value["stringKey"]
                original = texts[value["hash"]]
                for public, source in [("raw", "raw"), ("offset", "offset"), ("end", "end"), ("hasParams", "has_params")]:
                    assert value[public] == original[source]
                assert value["legacy"] == str(original["legacy"])
            expected_items = {r["ID"] for r in configs if (r["SetID"], r["Type"]) == (row["SetID"], row["Type"])}
            assert {r["itemId"] for r in record["itemDescriptionHashBindings"]} == expected_items
            for proof in record["itemDescriptionHashBindings"]:
                config = configs[int(proof["relicConfigPointer"].strip("/"))]
                item = items[int(proof["itemConfigPointer"].split("/")[1])]
                assert config["ID"] == item["ID"] == proof["itemId"]
                assert (config["SetID"], config["Type"]) == (row["SetID"], row["Type"])
                assert str(item["ItemBGDesc"]["Hash"]) == proof["hash"] == record["fields"]["ItemBGDesc"]["hash"]
                binding_count += 1
        assert binding_count == evidence["stringKeyBindingChecks"]
    assert args.input.read_bytes() == original_bytes and corpus() == evidence["preservedCorpus"]
    print(json.dumps({"status": "PASS", "scope": "official game pack full EOF + pinned metadata + existing item joins" if deep else "dataset + field bindings + preserved documents",
                      "sha256": digest(original_bytes), "counts": data["counts"], "mutationRejections": 3}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=SITE / "data/relic-backgrounds.json")
    parser.add_argument("--official-root", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--skill", type=Path)
    main(parser.parse_args())
