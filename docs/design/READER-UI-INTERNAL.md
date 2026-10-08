# Shared reader UI contract, 2026-10-08

The user reported the broken original reader at quest-1000400.html#original. In the actual 1025px in-app browser, the scene-index summary inherited a -9px inline margin from Starlight Markdown. The native disclosure marker sat outside its border. Framework sibling margins also applied inside filters and source scenes.

Reading-kit 1.4.0 owns source-reader boundaries, row kinds, disclosure HTML and geometry. Both repositories consume identical reader.mjs, reader.css and the existing editorial/topology templates, checked by the shared manifest. Astro and the Wuwa generator remain adapters for game-specific original text, provenance, anchors and filtering.

Custom reader and relationship roots use not-content. Native disclosure markers use one immediate summary, inside placement, zero inline margin and a 44px minimum target. General Markdown retains Starlight's own disclosure treatment. Source rows keep original strings and anchors. Transcript mode preserves Wuwa's existing speaker/body columns. Filter controls use the reader's available width and move the reset action below the two fields in narrow columns. Header/sidebar geometry is defined in the same shared CSS.

Whole-source validation after the first build passed: Star Rail 1284 missions, 101168 original rows, 101173 paragraph spans, 8817 progress anchors; Wuwa 766 quests, 9331 scenes, 97860 visible source lines. Static template QA is part of the existing original-rendering gates. Shared unit tests verify attribute escaping, one summary, accepted row kinds and measured-layout rejection cases.

Real UI evidence is collected through the existing in-app browser, separately from static QA. The first 13 measurements cover Star Rail 320/390/768/1025/1489px and Wuwa 320/390/1025px, native open/closed states and light/dark appearances. Measured bounds, target heights, summary style and document widths passed layout-qa.mjs. Enter/Space toggling was directly exercised. Evidence: D:/game/.codex-work/reader-layout-samples.json and reader-layout-results.json. The final merge-ref build and public browser verification are recorded in the work ledger.

Future reader adapters consume readerAttributes/rowAttributes/disclosureAttributes or readerFrame/readerDisclosure. Site-wide source QA checks the built HTML boundaries and immediate summaries. For CSS/layout changes, collect actual browser rectangles and computed styles into layout-qa.mjs's schema; unit fixtures alone establish only the validator's behavior. Verify long Korean dialogue, choice/gap rows, long provenance IDs, filters, folded source anchors, keyboard and source→setting→source→catalogue return.

This report is excluded from public content and search inputs. Current game-file coverage limits and the wider editorial backlog remain in the existing source reports.
