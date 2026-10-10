"""Verify complete discovery data and generated HTML against preserved originals.

This checks source membership, SSR content and stable addresses. It does not
establish browser layout, interactive filtering or current-installation coverage.
An optional pinned archive replays the universe grouping metadata without writes.
"""
import argparse
import copy
import hashlib
from html import escape
import json
import re
import sys
import tarfile
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from verify_universe_source_site import SourcePage, VOID

SITE = Path(__file__).resolve().parents[1]
BASE = "/starrail-quests/"
KINDS = {"person", "faction", "region", "concept", "mechanic", "reading-instruction"}
AXES = {"region", "person", "faction", "concept", "aeon", "reference"}
ITEM_CATEGORIES = {"아이템 설정", "유물 이야기", "광추 이야기", "시뮬레이션 우주 설정"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def unique(items, label):
    require(len(items) == len(set(items)), label + ": duplicate membership")


def address(url):
    value = urlsplit(url)
    require(not value.scheme and not value.netloc, "Unexpected external discovery URL: " + url)
    path = unquote(value.path)
    if path.startswith(BASE):
        path = path[len(BASE):]
    return path.lstrip("/"), unquote(value.fragment)


def classify(entry, rule):
    if not rule:
        return entry["axis"]
    if rule.get("subjectType") == "aeon":
        return "aeon"
    return "reference" if rule["kind"] in {"mechanic", "reading-instruction"} else rule["kind"]


def check_registry(registry, explorer, docs):
    require(registry["schema"] == "starrail-directory-discovery.v1", "Registry schema")
    groups = [g["id"] for g in registry["groups"]]
    unique(groups, "Registry groups")
    require(all(g.get("title") and g.get("summary") for g in registry["groups"]), "Empty group heading/context")
    rules = registry["rows"]
    unique([r["id"] for r in rules], "Registry rows")
    expected = {e["id"] for e in explorer if e["axis"] == "concept"}
    require(len(expected) == 416 and {r["id"] for r in rules} == expected, "All 416 LoadingDesc records must be classified")
    entries = {e["id"]: e for e in explorer}
    for rule in rules:
        rid = rule["id"]
        require(rule["kind"] in KINDS and rule["group"] in groups, rid + ": invalid kind/group")
        document = docs[rid]
        source_rows = [(s, r) for s in document["sections"] for r in s["rows"]]
        require(len(source_rows) == 1, rid + ": LoadingDesc source shape changed")
        section, original = source_rows[0]
        require(rule["name"] == document["title"] == entries[rid]["name"], rid + ": original name differs")
        require(rule["quote"] == original["text"] == entries[rid]["excerpt"], rid + ": original quote differs")
        require(str(rule["hash"]) == str(original["hash"]), rid + ": original hash differs")
        require(rule["source"] == original["source"] == "LoadingDesc:" + rid[5:] + ".DescTextmapID", rid + ": source field differs")
        require(address(rule["url"]) == (document["url"], section["anchor"] + "-row-1"), rid + ": original address differs")
    index = {r["id"]: r for r in rules}
    for rid, kind, group in [
        ("lore-10023", "person", "hunters"), ("lore-10432", "region", "train"),
        ("lore-10048", "faction", "factions"), ("lore-10059", "faction", "memory"),
        ("lore-10018", "person", "station"), ("lore-10019", "person", "station"),
        ("lore-10024", "person", "station"), ("lore-10141", "person", "research"),
        ("lore-10142", "person", "research"), ("lore-10130", "reading-instruction", "instructions"),
        ("lore-10214", "concept", "xianzhou"),
    ]:
        require((index[rid]["kind"], index[rid]["group"]) == (kind, group), rid + ": source classification canary differs")
    require(index["lore-10084"].get("subjectType") == "aeon", "Named Aeon classification is missing")
    require(index["lore-10229"].get("subjectType") == "multiple-named-persons", "Three-person source scope is missing")
    return index


def check_identities(registry, explorer):
    identities = registry.get('identities', [])
    unique([i['id'] for i in identities], 'Source identities')
    effective = copy.deepcopy(explorer)
    by_id = {e['id']: e for e in effective}
    for identity in identities:
        entry = by_id.get(identity['id'])
        require(entry is not None and entry['axis'] == 'person' and entry['source'] == 'StoryAtlas'
                and not entry.get('nameVerified'), 'Identity source/subject differs')
        stories = [s for s in entry['stories'] if s['story_id'] == identity['storyId']]
        require(len(stories) == 1 and type(identity['storyId']) is int and identity['storyId'] > 0,
                'Identity story missing/ambiguous')
        name, quote, original_hash = identity['name'], identity['quote'], identity['hash']
        require(isinstance(name, str) and name.strip() and isinstance(quote, str)
                and isinstance(original_hash, str) and original_hash.isdecimal(), 'Identity format differs')
        require(str(stories[0]['hash']) == original_hash and quote.startswith(name + ',')
                and quote in stories[0]['text'], 'Identity quotation/hash differs')
        entry['name'] = name
    return effective


def check_identity_html(dist, registry, explorer, docs):
    endpoint = read(dist / 'atlas-data.json')
    graph = {e['id']: e for e in read(dist / 'reading-data/graph.json')['entities']}
    for identity in registry.get('identities', []):
        rid = identity['id']
        page = parsed((dist / '대상' / (rid + '.html')).read_text(encoding='utf-8'))
        require(endpoint[rid]['name'] == graph[rid]['name'] == identity['name'], 'Reader identity endpoint differs')
        require(any(n['tag'] == 'h1' and n['text'].strip() == identity['name'] for n in page.nodes), 'Identity heading missing')
        require(any(n['tag'] == 'a' and n['attrs'].get('href') == '#story-' + str(identity['storyId']) for n in page.nodes), 'Identity evidence story link missing')
        require(any(n['tag'] == 'a' and 'context-term' in n['attrs'].get('class', '').split()
                    and n['attrs'].get('data-context-key') == rid
                    and n['text'] == identity['name'] and address(n['attrs']['href']) == ('대상/' + rid + '.html', '')
                    for n in page.nodes), 'Evidence-based name unavailable to original inline links')
    for rid, anchor, wrong_target in [('lore-10035', 'section-1-row-1', '맥락/family.html'),
                                      ('book-30', 'section-2-row-1', '대상/aeon-aeon-4.html')]:
        page = parsed((dist / '문서' / (rid + '.html')).read_text(encoding='utf-8'))
        rows = [n for n in page.nodes if n['attrs'].get('id') == anchor]
        require(len(rows) == 1, 'Homonym source row missing')
        require(not any(n['tag'] == 'a' and address(n['attrs']['href'])[0] == wrong_target for n in descendants(rows[0])),
                rid + ': ordinary noun still links to unrelated subject')
        require(page.original[anchor] == next(r['text'] for s in docs[rid]['sections'] for index, r in enumerate(s['rows'], 1)
                                            if s['anchor'] + '-row-' + str(index) == anchor), 'Homonym original changed')


def expected_discovery(explorer, registry, atlas, faction_doc):
    result = {}
    for entry in explorer:
        rule = registry.get(entry["id"])
        result[entry["id"]] = {"id": entry["id"], "name": entry["name"], "axis": classify(entry, rule),
                               "group": rule["group"] if rule else "source-" + entry["axis"],
                               "url": ("문서/" if entry["axis"] == "concept" else "대상/") + entry["id"] + ".html",
                               "search": entry["excerpt"]}
    for node in atlas["nodes"]:
        axis = "concept" if node.get("directoryKind") == "종족" else "faction" if node["axis"] == "bridge" else node["axis"]
        rid = "atlas-" + node["id"]
        require(rid not in result, "Curated ID collision")
        result[rid] = {"id": rid, "name": node["name"], "axis": axis, "group": "curated-" + axis,
                       "url": "맥락/" + node["id"] + ".html", "search": node["intro"],
                       "summary": node.get("directorySummary") or node["intro"]}
    for section in faction_doc["sections"][2:]:
        rid = "book-47-" + section["anchor"]
        result[rid] = {"id": rid, "name": section["title"], "axis": "faction", "group": "archive-factions",
                       "url": faction_doc["url"] + "#" + section["anchor"] + "-row-1",
                       "search": "\n".join(r["text"] for r in section["rows"])}
    require(len(explorer) == 530 and len(atlas["nodes"]) == 36 and len(faction_doc["sections"][2:]) == 21, "Preserved 530+36+21 subject inputs differ")
    require(len(result) == 587 and {r["axis"] for r in result.values()} == AXES, "Complete six-axis discovery membership differs")
    require(result["atlas-borisin"]["axis"] == "concept", "Species classified as an organization")
    return result


def expected_items(catalog, universe, backgrounds, docs):
    preserved = {d["id"] for d in catalog if d["category"] in ITEM_CATEGORIES}
    require(len(preserved) == 3597, "Preserved item source count differs")
    collection_ids = [d["id"] for c in universe["itemCollections"] for d in c["documents"]]
    unique(collection_ids, "Item collections")
    require(set(collection_ids) == preserved, "Item collections omitted/added original documents")
    result = {}
    for collection in universe["itemCollections"]:
        for item in collection["documents"]:
            original = docs[item["id"]]
            texts = [r["text"] for s in original["sections"] for r in s["rows"] if r["text"]]
            name_only = bool(texts) and all(t.strip() == item["title"].strip() for t in texts)
            result[item["id"]] = {"id": item["id"], "name": item["title"], "axis": "", "url": original["url"],
                                  "group": "item-names" if name_only else collection["id"], "search": texts[0] if texts else ""}
    ids = [r["id"] for r in backgrounds["records"]]
    unique(ids, "Relic backgrounds")
    require(len(ids) == 192, "All 192 relic stories must be preserved")
    linked = set()
    for record in backgrounds["records"]:
        require(record["text"] == record["fields"]["BGStoryContent"]["text"], record["id"] + ": long original differs")
        for proof in record["relatedItemMappings"]:
            doc = docs[proof["documentId"]]
            require(doc["id"] in preserved and doc["category"] == "유물 이야기", "Relic bound to another category")
            require(doc["title"] == record["title"], "Relic title binding differs")
            require(any(r["text"] == record["fields"]["ItemBGDesc"]["text"] and str(r["hash"]) == proof["hash"]
                        and r["source"].endswith(".ItemBGDesc") for s in doc["sections"] for r in s["rows"]), "Relic short source binding differs")
            linked.add(doc["id"])
        result[record["id"]] = {"id": record["id"], "name": record["title"], "axis": "", "group": "relic-backgrounds",
                                "url": "유물/" + record["id"] + ".html", "search": record["text"]}
    require(linked == {d["id"] for d in catalog if d["category"] == "유물 이야기"} and len(linked) == 184, "All 184 short originals must have exact long-story joins")
    collections = backgrounds["collections"]
    unique([c["id"] for c in collections], "Relic sets")
    require(len(collections) == 62, "All 62 relic sets must be preserved")
    assigned = [rid for c in collections for rid in c["recordIds"]]
    unique(assigned, "Relic set membership")
    require(set(assigned) == set(ids), "Relic set record membership differs")
    for collection in collections:
        require(collection["name"] == collection["field"]["text"] and collection["field"]["fieldKey"] == "SetName", "Relic set original name differs")
        require(collection["recordIds"] == [r["id"] for r in backgrounds["records"] if r["sourceRowId"]["setId"] == collection["setId"]], "Relic set/part binding differs")
    require(len(result) == 3789, "Complete item and relic discovery membership differs")
    return result


def check_universe(discovery, sources, official, source_bytes, official_bytes, metadata=None):
    require(discovery["schema"] == "starrail-universe-discovery.v1", "Universe discovery schema")
    evidence = discovery["evidence"]
    require(evidence["sourceRecordsSha256"] == sha(source_bytes), "Universe preserved record bytes differ")
    require(evidence["officialUniverseSha256"] == sha(official_bytes), "Universe official field bytes differ")
    require(evidence["metadataCommit"] == sources["evidence"]["commit"] and evidence["archiveSha256"] == sources["evidence"]["archiveSha256"], "Universe metadata provenance differs")
    originals = {r["id"]: r for m in sources["modes"] for r in m["records"]}
    modes = {m["id"]: m for m in sources["modes"]}
    unique([m["modeId"] for m in discovery["items"]], "Universe discovery modes")
    require({m["modeId"] for m in discovery["items"]} == set(modes), "Universe modes omitted/added")
    official_by_id = {r["id"]: r for r in official["records"]}
    grouped, edge_count = [], 0
    for mode in discovery["items"]:
        expected = {r["id"] for r in modes[mode["modeId"]]["records"]}
        assigned = [rid for g in mode["groups"] for rid in g["recordIds"]]
        unique([g["id"] for g in mode["groups"]], "Universe group IDs")
        unique(assigned, mode["modeId"] + " groups")
        require(set(assigned) == expected, mode["modeId"] + ": source grouping omitted/added records")
        require({r["id"] for r in mode["records"]} == expected, "Universe displayed record membership differs")
        unique([r["id"] for r in mode["records"]], "Universe display records")
        for record in mode["records"]:
            original = originals[record["id"]]
            proof = record["evidence"]
            require(proof["table"] == original["sourceTable"] and proof["sourceSha256"] == original["sourceSha256"], "Universe record source table/hash differs")
            require(proof["pointer"] == f"/{original['sourceRow']}/{original['idField']}" and proof["value"] == original["sourceRecordId"], "Universe record identity differs")
            if metadata is not None:
                require(pointer(metadata[proof["table"]], proof["pointer"]) == proof["value"], "Pinned universe record identity differs")
            for oid in record.get("officialRecordIds", []):
                require(oid in official_by_id and record["id"] in official_by_id[oid]["linkedSourceRecordIds"], "Universe name/body join differs")
        for group in mode["groups"]:
            require(group["title"] and group["titleKind"] in {"original", "editorial-directory-label"}, "Universe title attribution differs")
            for proof in group["evidence"]:
                require(proof["sourceSha256"] == evidence["metadataFiles"][proof["table"]], "Universe group source checksum differs")
                if metadata is not None:
                    require(pointer(metadata[proof["table"]], proof["pointer"]) == proof["value"], "Universe group source value differs")
            if mode["modeId"] == "swarm-disaster":
                listed = next(p["value"] for p in group["evidence"] if p["field"] == "SubStoryList")
                require(group["recordIds"] == ["swarm-disaster-" + str(i) for i in listed], "Swarm containment list differs")
                require(group["nameEvidence"]["text"] == group["title"], "Swarm original group title differs")
                if metadata is not None:
                    name = group["nameEvidence"]
                    require(str(pointer(metadata[name["table"]], name["pointer"])["Hash"]) == name["hash"], "Swarm group title hash differs")
        edge_ids = []
        for edge in mode["edges"]:
            edge_ids.append((edge["from"], edge["to"]))
            require(edge["from"] in expected and edge["to"] in expected, "Universe edge endpoint differs")
            origin, target = originals[edge["from"]], originals[edge["to"]]
            proof = edge["evidence"]
            next_ids = origin["recordMetadata"].get("NextIDList", [])
            require(edge["kind"] == "explicit-next-record" and target["sourceRecordId"] in next_ids, "Universe edge direction differs from source NextIDList")
            index = next_ids.index(target["sourceRecordId"])
            require(proof["table"] == origin["sourceTable"] and proof["sourceSha256"] == origin["sourceSha256"]
                    and proof["pointer"] == f"/{origin['sourceRow']}/NextIDList/{index}" and proof["value"] == target["sourceRecordId"], "Universe next-record pointer differs")
            if metadata is not None:
                require(pointer(metadata[proof["table"]], proof["pointer"]) == proof["value"], "Pinned next-reference direction differs")
            require(edge.get("conditionSubject") == edge["to"], "Next-record condition attached to the wrong subject")
            condition = edge["conditionEvidence"]
            matching = [field for record in official["records"] if edge["to"] in record["linkedSourceRecordIds"] for field in record["fields"] if field["fieldKey"] == "TriggerCondition"]
            require(len(matching) == 1, "Next-record condition source missing/ambiguous")
            field = matching[0]
            require(condition["table"] == target["sourceTable"] and condition["sourceSha256"] == target["sourceSha256"]
                    and condition["pointer"] == field["sourcePointer"] == f"/{target['sourceRow']}/TriggerCondition"
                    and condition["hash"] == field["textmapHash"] and condition["raw"] == field["raw"]
                    and condition["text"] == field["text"] == edge["condition"], "Next-record original condition differs")
            if metadata is not None:
                require(str(pointer(metadata[condition["table"]], condition["pointer"])["Hash"]) == condition["hash"], "Pinned next-reference condition hash differs")
        unique(edge_ids, "Universe edges")
        grouped.extend(assigned)
        edge_count += len(edge_ids)
    unique(grouped, "All universe grouped records")
    require(len(grouped) == 128 and set(grouped) == set(originals), "All 128 universe source records must be preserved")
    swarm = next(m for m in discovery["items"] if m["modeId"] == "swarm-disaster")
    require(len(swarm["groups"]) == 14 and edge_count == 18, "Source swarm group / gold progression coverage differs")
    return originals


def pointer(value, path):
    for part in path.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


class DiscoveryPage(SourcePage):
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.roots = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        super().handle_starttag(tag, attrs)
        node = self.stack[-1] if tag not in VOID and self.stack and self.stack[-1]["tag"] == tag else {"tag": tag, "attrs": values, "text": "", "children": []}
        self.nodes.append(node)
        if "data-grouped-directory" in values:
            self.roots[values["id"]] = node


def parsed(text):
    page = DiscoveryPage()
    page.feed(text)
    page.close()
    require(not page.duplicates, "Duplicate stable HTML anchors: " + str(page.duplicates[:3]))
    require(not page.nested_p, "Nested original paragraphs")
    return page


def descendants(node):
    for child in node["children"]:
        yield child
        yield from descendants(child)


def check_directory(page, scope, expected, default_axis=None):
    require(scope in page.roots, scope + ": missing SSR directory")
    root = page.roots[scope]
    if default_axis is not None:
        require(root["attrs"].get("data-default-axis") == default_axis, scope + ": SSR page axis differs")
    nodes = list(descendants(root))
    cards = [n for n in nodes if "data-directory-entry" in n["attrs"]]
    actual_ids = [n["attrs"]["data-directory-entry"] for n in cards]
    unique(actual_ids, scope + " SSR subjects")
    require(set(actual_ids) == set(expected), scope + ": SSR subjects omitted/added")
    groups = [n for n in nodes if "data-directory-section" in n["attrs"]]
    unique([n["attrs"]["data-directory-section"] for n in groups], scope + " SSR groups")
    for card in cards:
        rid = card["attrs"]["data-directory-entry"]
        original = expected[rid]
        attrs = card["attrs"]
        require(attrs["data-directory-axis"] == original["axis"] and attrs["data-directory-group"] == original["group"], rid + ": SSR classification differs")
        links = [n for n in descendants(card) if n["tag"] == "a" and "data-reading-link" in n["attrs"]]
        require(len(links) == 1 and links[0]["attrs"].get("id") == scope + "-entry-" + rid, rid + ": missing/duplicate stable subject link")
        require(address(links[0]["attrs"]["href"]) == address(original["url"]), rid + ": wrong individual body/anchor")
        require(original["name"] in card["text"], rid + ": missing SSR subject title")
        require(original["search"] in attrs["data-directory-search"], rid + ": source content omitted from search")
        if "summary" in original:
            require(original["summary"] in card["text"], rid + ": edited summary missing from SSR card")
        if default_axis is not None:
            require(("hidden" in attrs) == (original["axis"] != default_axis), rid + ": SSR default axis visibility differs")
    for group in groups:
        gid = group["attrs"]["data-directory-section"]
        assigned = [n["attrs"]["data-directory-entry"] for n in descendants(group) if "data-directory-entry" in n["attrs"]]
        require(set(assigned) == {rid for rid, e in expected.items() if e["group"] == gid}, gid + ": entries outside their source group")
        require(group["attrs"]["id"] == scope + "-group-" + gid, gid + ": unstable group anchor")
        require(any(n["tag"] == "h3" and n["text"].strip() for n in descendants(group)), gid + ": missing group heading")
    require({g["attrs"]["data-directory-section"] for g in groups} == {e["group"] for e in expected.values()}, scope + ": missing complete group")
    require(any(n["attrs"].get("role") == "status" and n["attrs"].get("aria-live") == "polite" for n in nodes), scope + ": missing result announcement")


def check_html(dist, expected, items, backgrounds, universe_discovery, sources):
    def page(relative):
        path = dist / relative
        require(path.exists(), "Missing generated page: " + relative)
        return parsed(path.read_text(encoding="utf-8"))
    check_directory(page("설정집.html"), "explore", {rid: e for rid, e in expected.items() if e["axis"] == "region"}, "region")
    discovered = []
    for axis in sorted(AXES):
        rendered = page("관점/" + axis + ".html")
        subset = {rid: e for rid, e in expected.items() if e["axis"] == axis}
        check_directory(rendered, "explore", subset, axis)
        discovered.extend(n["attrs"]["data-directory-entry"] for n in descendants(rendered.roots["explore"]) if "data-directory-entry" in n["attrs"])
    unique(discovered, "Six-axis SSR source membership")
    require(set(discovered) == set(expected), "Six-axis SSR union must preserve every original, curated and verified added subject exactly once")
    check_directory(page("세력.html"), "factions", {i: e for i, e in expected.items() if e["axis"] == "faction"})
    item_page = page("우주.html")
    check_directory(item_page, "item-library", items)
    require(any(address(url)[0] == "유물.html" for url in item_page.links if not urlsplit(url).scheme), "Missing set-library entry from item hub")
    set_items = {rid: {**items[rid], "group": c["id"]} for c in backgrounds["collections"] for rid in c["recordIds"]}
    set_page = page("유물.html")
    check_directory(set_page, "relic-library", set_items)
    for collection in backgrounds["collections"]:
        group = next(n for n in descendants(set_page.roots["relic-library"]) if n["attrs"].get("data-directory-section") == collection["id"])
        headings = [n["text"] for n in descendants(group) if n["tag"] == "h3"]
        require(headings == [collection["name"]], collection["id"] + ": set name omitted/changed in SSR heading")
    checked_docs = {}
    for record in backgrounds["records"]:
        rendered = page("유물/" + record["id"] + ".html")
        require(rendered.original.get(record["id"] + "-body") == record["text"], record["id"] + ": complete long story differs in HTML")
        same_set = next((n for n in rendered.nodes if n["attrs"].get("id") == "same-set"), None)
        require(same_set is not None, record["id"] + ": missing same-set navigation")
        collection = next(c for c in backgrounds["collections"] if c["setId"] == record["sourceRowId"]["setId"])
        require(any(n["tag"] == "h2" and n["text"] == collection["name"] for n in descendants(same_set)), record["id"] + ": missing original set name")
        require(any(address(url) == ("유물.html", "relic-library-group-" + collection["id"])
                    and parse_qs(urlsplit(url).query).get("relicSet") == [collection["id"]]
                    for url in rendered.links if not urlsplit(url).scheme), record["id"] + ": missing set-filter reader return")
        peers = {"유물/" + r["id"] + ".html" for r in backgrounds["records"] if r["sourceRowId"]["setId"] == record["sourceRowId"]["setId"] and r["id"] != record["id"]}
        actual = {address(n["attrs"]["href"])[0] for n in descendants(same_set) if n["tag"] == "a" and "data-reading-link" in n["attrs"]}
        require(actual == peers, record["id"] + ": same-set source membership differs in HTML")
        for did in record["relatedItemIds"]:
            if did not in checked_docs:
                checked_docs[did] = page("문서/" + did + ".html")
            linked = checked_docs[did]
            require(any(address(url)[0] == "유물/" + record["id"] + ".html" for url in linked.links if not urlsplit(url).scheme), did + ": missing long-story reader link")
    originals = {r["id"]: r for mode in sources["modes"] for r in mode["records"]}
    for mode in universe_discovery["items"]:
        rendered = page("우주/" + mode["modeId"] + ".html")
        markers = [n for n in rendered.nodes if "data-universe-source-group" in n["attrs"]]
        require({n["attrs"]["data-universe-source-group"] for n in markers} == {g["id"] for g in mode["groups"]}, mode["modeId"] + ": source group SSR membership differs")
        unique([n["attrs"]["data-universe-source-group"] for n in markers], "Universe SSR groups")
        titles = {r["id"]: r for r in mode["records"]}
        ordered = [r["id"] for m in sources["modes"] if m["id"] == mode["modeId"] for r in m["records"]]
        named = []
        for marker in markers:
            group = next(g for g in mode["groups"] if g["id"] == marker["attrs"]["data-universe-source-group"])
            require(marker["attrs"].get("id") == "universe-record-directory-" + mode["modeId"] + "-group-" + group["id"], group["id"] + ": unstable universe group anchor")
            links = [n for n in descendants(marker) if "data-source-record" in n["attrs"]]
            require([n["attrs"]["data-source-record"] for n in links] == group["recordIds"], group["id"] + ": SSR records omitted/duplicated/reordered")
            require(group["title"] in marker["text"], group["id"] + ": missing original/editorial group title")
            for node in links:
                attrs = node["attrs"]
                rid = attrs["data-source-record"]
                named.append(rid)
                require(node["tag"] == "a" and attrs.get("id") == "universe-source-" + rid and "data-reading-link" in attrs, rid + ": source reader link/anchor differs")
                require(address(attrs["href"]) == ("우주/기록/" + rid + ".html", ""), rid + ": wrong universe reader target")
                require(attrs.get("data-search") == " ".join(row["text"] for scene in originals[rid]["scenes"] for row in scene["rows"]), rid + ": complete original omitted from universe search")
                require(attrs.get("data-source-group") == group["id"] and attrs.get("data-title-kind") == titles[rid]["titleKind"] and titles[rid]["title"] in node["text"], rid + ": universe title attribution differs")
                require(("hidden" in attrs) == (ordered.index(rid) >= 12), rid + ": default source batch visibility differs")
        require(named == ordered, mode["modeId"] + ": original source directory order differs")
        edges = [n for n in rendered.nodes if "data-universe-next-from" in n["attrs"]]
        require(Counter((n["attrs"]["data-universe-next-from"], n["attrs"].get("data-universe-next-to")) for n in edges) == Counter((e["from"], e["to"]) for e in mode["edges"]), mode["modeId"] + ": SSR progression references differ")
        bands = [n for n in rendered.nodes if "rw-relation-band" in n["attrs"].get("class", "").split()]
        require(Counter((n["attrs"].get("data-relation-from"), n["attrs"].get("data-relation-to")) for n in bands) == Counter((e["from"], e["to"]) for e in mode["edges"]), mode["modeId"] + ": visible progression references differ")
        for node in edges:
            edge = next(e for e in mode["edges"] if (e["from"], e["to"]) == (node["attrs"]["data-universe-next-from"], node["attrs"]["data-universe-next-to"]))
            require(node["attrs"].get("data-universe-next-condition-subject") == edge["to"]
                    and node["attrs"].get("data-universe-next-pointer") == edge["evidence"]["pointer"]
                    and node["attrs"].get("data-universe-next-value") == str(edge["evidence"]["value"]), "SSR next-reference direction/condition subject differs")
            band = next(n for n in bands if (n["attrs"].get("data-relation-from"), n["attrs"].get("data-relation-to")) == (edge["from"], edge["to"]))
            proofs = [n for n in descendants(band) if n["tag"] == "details" and "rw-relation-proof" in n["attrs"].get("class", "").split()]
            require(len(proofs) == 1, "Missing/duplicate visible next-reference source proof")
            proof_nodes = list(descendants(proofs[0]))
            codes = [n["text"] for n in proof_nodes if n["tag"] == "code"]
            require(edge["evidence"]["pointer"] in codes and str(edge["evidence"]["value"]) in codes
                    and edge["conditionEvidence"]["pointer"] in codes
                    and json.dumps(edge["conditionEvidence"]["raw"], ensure_ascii=False) in codes, "Visible next-reference original pointer/condition omitted")
            local_links = [address(n["attrs"]["href"]) for n in proof_nodes if n["tag"] == "a" and not urlsplit(n["attrs"]["href"]).scheme]
            require(("우주/기록/" + edge["from"] + ".html", "") in local_links and ("우주/기록/" + edge["to"] + ".html", "") in local_links, "Progression proof must link both exact original subjects")
            official_ids = titles[edge["to"]]["officialRecordIds"]
            require(any(("우주/설정/" + oid + ".html", "") in local_links for oid in official_ids), "Missing condition original reader link")
    return {"discoveryPages": 8, "itemPages": 1, "relicSetPages": 1, "relicPages": 192, "linkedShortOriginalPages": len(checked_docs), "universeModes": len(universe_discovery["items"])}


def self_test(registry, explorer, docs, universe_data, sources, official, source_bytes, official_bytes):
    rejected = []
    for label, mutate in [
        ('identity-wrong-story', lambda d: d['identities'][0].update(storyId=1)),
        ('identity-wrong-hash', lambda d: d['identities'][0].update(hash='1')),
        ('identity-invented-name', lambda d: d['identities'][0].update(name='가상의 이름')),
        ('identity-duplicate', lambda d: d['identities'].append(d['identities'][0])),
    ]:
        changed = copy.deepcopy(registry)
        mutate(changed)
        try:
            check_identities(changed, explorer)
        except (AssertionError, KeyError):
            rejected.append(label)
        else:
            raise AssertionError('Accepted negative fixture: ' + label)
    for label, mutate in [
        ("missing-original", lambda d: d["rows"].pop()),
        ("changed-quote", lambda d: d["rows"][0].update(quote=d["rows"][0]["quote"] + "x")),
        ("wrong-source-field", lambda d: d["rows"][0].update(source="LoadingDesc:10001.Title")),
        ("person-as-faction", lambda d: next(r for r in d["rows"] if r["id"] == "lore-10023").update(kind="faction")),
    ]:
        changed = copy.deepcopy(registry)
        mutate(changed)
        try:
            check_registry(changed, explorer, docs)
        except (AssertionError, KeyError):
            rejected.append(label)
        else:
            raise AssertionError("Accepted negative fixture: " + label)
    for label, mutate in [
        ("duplicate-universe-membership", lambda d: d["items"][0]["groups"][0]["recordIds"].append(d["items"][0]["groups"][0]["recordIds"][0])),
        ("reversed-next-reference", lambda d: next(m for m in d["items"] if m["modeId"] == "gold-and-gears")["edges"][0].update({"from": "gold-and-gears-2011", "to": "gold-and-gears-1001"})),
        ("wrong-condition-subject", lambda d: next(m for m in d["items"] if m["modeId"] == "gold-and-gears")["edges"][0].update(conditionSubject="gold-and-gears-1001")),
    ]:
        changed = copy.deepcopy(universe_data)
        mutate(changed)
        try:
            check_universe(changed, sources, official, source_bytes, official_bytes)
        except (AssertionError, KeyError):
            rejected.append(label)
        else:
            raise AssertionError("Accepted negative fixture: " + label)
    try:
        parsed('<section id="same"></section><section id="same"></section>')
    except AssertionError:
        rejected.append("duplicate-html-anchor")
    else:
        raise AssertionError("Accepted duplicate stable anchor")
    fixtures = {"fixture-" + str(i): {"id": "fixture-" + str(i), "name": "제목 " + str(i), "axis": "person", "group": "same",
                                   "url": "문서/fixture-" + str(i) + ".html", "search": "원문 " + str(i)} for i in range(25)}
    def card(rid):
        e = fixtures[rid]
        return ('<article data-directory-entry="' + rid + '" data-directory-axis="person" data-directory-group="same" data-directory-search="' + escape(e["search"], quote=True) + '">'
                '<a id="fixture-entry-' + rid + '" data-reading-link href="' + e["url"] + '">' + e["name"] + '</a></article>')
    def fixture(cards):
        return '<section id="fixture" data-grouped-directory data-default-axis="person"><p role="status" aria-live="polite"></p><section id="fixture-group-same" data-directory-section="same"><h3>같은 묶음</h3>' + ''.join(cards) + '</section></section>'
    cards = [card(rid) for rid in fixtures]
    healthy = fixture(cards)
    check_directory(parsed(healthy), "fixture", fixtures, "person")
    for label, malformed in [("omitted-second-cva-batch", fixture(cards[:24])),
                              ("duplicated-second-cva-batch", fixture(cards[:24] + [cards[0]])),
                              ("wrong-individual-reader", healthy.replace('href="문서/fixture-24.html"', 'href="문서/fixture-0.html"')),
                              ("wrong-ssr-axis", healthy.replace('data-directory-axis="person"', 'data-directory-axis="faction"', 1)),
                              ("hidden-other-axis-index-leak", fixture(cards + [cards[0].replace('fixture-0', 'other-region').replace('data-directory-axis="person"', 'data-directory-axis="region" hidden')]))]:
        try:
            check_directory(parsed(malformed), "fixture", fixtures, "person")
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError("Accepted negative fixture: " + label)
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=SITE / "dist")
    parser.add_argument("--artifact-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--archive", type=Path, help="Optional exact metadata archive; only five declared tables are read")
    args = parser.parse_args()
    registry = read(SITE / "editorial/directory-discovery.json")
    explorer = read(SITE / "data/explorer.json")["entries"]
    catalog = read(SITE / "data/catalog.json")
    docs = {d["id"]: read(SITE / "data/documents" / (d["id"] + ".json")) for d in catalog}
    rules = check_registry(registry, explorer, docs)
    effective_explorer = check_identities(registry, explorer)
    expected = expected_discovery(effective_explorer, rules, read(SITE / "editorial/context-atlas.json"), docs["book-47"])
    backgrounds = read(SITE / "data/relic-backgrounds.json")
    items = expected_items(catalog, read(SITE / "data/universe-catalog.json"), backgrounds, docs)
    # Preserve the exact baseline membership checks above, then add the manifest-
    # bound handbook originals. Their raw source replay is a separate strong gate.
    handbook = read(SITE / "data/handbook-originals.json")
    from verify_handbook_originals import artifact_check
    artifact_check(handbook)
    for d in handbook['documents']:
        if d['category']=='캐릭터 이야기':
            aid=d['sections'][0]['rows'][0]['avatar_id'];rid='person-'+str(aid)
            require(rid not in expected,'Handbook person overwrites a preserved discovery subject')
            expected[rid]={'id':rid,'name':d['title'],'axis':'person','group':'source-person','url':'대상/'+rid+'.html','search':d['sections'][0]['rows'][0]['text'][:220]}
        if d['category'] in ('광추 이야기','아이템 설정'):
            require(d['id'] not in items,'Handbook item overwrites a preserved subject')
            items[d['id']]={'id':d['id'],'name':d['title'],'axis':'','group':'light-cones' if d['category']=='광추 이야기' else 'items','url':d['url'],'search':d['sections'][0]['rows'][0]['text']}
    source_bytes = (SITE / "data/universe-source-records.json").read_bytes()
    official_bytes = (SITE / "data/official-universe-texts.json").read_bytes()
    sources, official = json.loads(source_bytes), json.loads(official_bytes)
    universe = read(SITE / "data/universe-discovery.json")
    metadata = None
    if args.archive:
        require(sha(args.archive.read_bytes()) == universe["evidence"]["archiveSha256"], "Pinned metadata archive bytes differ")
        metadata = {}
        with tarfile.open(args.archive, "r:gz") as archive:
            for member in archive:
                name = member.name.split("/", 1)[-1]
                if name in universe["evidence"]["metadataFiles"]:
                    raw = archive.extractfile(member).read()
                    require(sha(raw) == universe["evidence"]["metadataFiles"][name], "Pinned table bytes differ: " + name)
                    metadata[name] = json.loads(raw)
        require(set(metadata) == set(universe["evidence"]["metadataFiles"]), "Missing pinned metadata tables")
    check_universe(universe, sources, official, source_bytes, official_bytes, metadata)
    negatives = self_test(registry, explorer, docs, universe, sources, official, source_bytes, official_bytes) if args.self_test else []
    rendered = {} if args.artifact_only else check_html(args.dist, expected, items, backgrounds, universe, sources)
    if not args.artifact_only:
        check_identity_html(args.dist, registry, explorer, docs)
    print(json.dumps({"status": "PASS", "scope": "artifact data" if args.artifact_only else "artifact data and generated HTML; browser runtime/layout not assessed",
                      "classifiedOriginals": len(rules), "discoverySubjects": len(expected), "axes": dict(Counter(e["axis"] for e in expected.values())),
                      "itemSubjects": len(items), "relicStories": 192, "relicSets": 62, "universeSourceRecords": 128,
                      "metadataReplayed": bool(metadata), "negativeFixturesRejected": negatives, "generated": rendered}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, ValueError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        sys.exit(1)
