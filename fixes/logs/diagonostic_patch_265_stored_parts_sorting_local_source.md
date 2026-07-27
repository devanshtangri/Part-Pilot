# Patch 265 Stored Parts Sorting Diagnostic

Generated: `2026-07-27T20:27:10`

## Purpose

Patches 259 and 260 failed before writes because separate transforms assumed
exact local adjacency. Patch 261 failed at Python parse time. Patch 262 completed
inspection but its staged report failed whitespace validation. Patch 263 was
blocked because two committed documentation files were unexpectedly deleted.
Patch 264 restored those files. This report is a read-only snapshot of the
authoritative local source and deployment before sorting implementation resumes.

## Repository and Git index

- Root: `/projects/Part Pilot`
- Branch: `main`
- Origin: `github.com/devanshtangri/Part-Pilot`
- Local HEAD: `3ed68d1293219b4bb792860c9c05e98e1a651b0f`
- origin/main: `3ed68d1293219b4bb792860c9c05e98e1a651b0f`
- Pending paths: `['frontend/src/pages/PartManager.css', 'frontend/src/pages/PartManager.tsx']`
- Staged pending paths: `[]`
- Unstaged pending paths: `['frontend/src/pages/PartManager.css', 'frontend/src/pages/PartManager.tsx']`
- Application index signature SHA-256:
  `5618255ce83fb51f4038634607c632375f19153c411c84776ed9aa4c4685a923`

## Pending application preservation

- `PartManager.tsx` SHA-256:
  `5aaf01b22a7a1a84e2a5bdc87cf9da4dda6840889cf532cc5911e35b62a9a4aa`
- `PartManager.css` SHA-256:
  `26de80fbb88d30cfde437d3b2ade0a8c3092a6c885bee25cb12d4e400e5fc317`
- `frontend/src/pages/PartManager.css` diff SHA-256: `681f12094221eae5f419c9bca65165ef8360b5b305824e8d458a11afa5cffd9a`; bytes: 17720
- `frontend/src/pages/PartManager.tsx` diff SHA-256: `36d8e2798641bc46ad311d519b3cc1d30c4784d49e290d7077b037e02e50e516`; bytes: 16063
- Failed Patch 259/260 sorting markers are absent.
- Patch 265 does not modify or stage either application file.

## Deployment

```json
{
  "container_id": "9b2acc0785bce6ebeae0eeeafc84b8324d089b04d9ba77b185e6678dd86533c4",
  "deployed_marker_counts": {
    "PARTPILOT_STORED_PARTS_SORT_V259": 0,
    "PARTPILOT_STORED_PARTS_SORT_V260": 0,
    "partpilot.inventory.page-size": 1,
    "stored-parts-available-card-v258": 1,
    "stored-parts-out-of-stock-card-v257": 1,
    "stored-parts-preference-v248": 3,
    "stored-parts-row-polish-v258": 1,
    "stored-parts-table-sorting-v259": 0,
    "stored-parts-table-sorting-v260": 0
  },
  "host_port": 7890,
  "image_id": "sha256:f7ff6d5aa3a9c29c3d6b83e6d93970b254fa76d75b4468ab0dc3703a48a9cf7d",
  "image_name": "partpilot-partpilot",
  "running": true
}
```

## Database and temporary fixtures

```json
{
  "alembic_head": "0005_packages",
  "database_path": "/projects/Part Pilot/data/partpilot.db",
  "database_sha256": "ea9cc2f84f866262184f492f53876a1c8b62d1db9888e10b36531f3db6391aa2",
  "fixture_count": 70,
  "fixture_package_columns": [
    "package"
  ],
  "fixture_packages_null": true,
  "integrity": "ok",
  "manifest_path": "/projects/Part Pilot/fixes/logs/patch_241_stored_parts_fixture_manifest.json",
  "manifest_sha256": "e5da46310f703bea03c9a0acf62efb9f12559efab92b43d711721d03d6c76ff6",
  "parts_count": 79
}
```

- Manifest-owned fixture IDs: 70
- First IDs: `[10, 11, 12, 13, 14, 15, 16, 17, 18, 19]`
- Last IDs: `[70, 71, 72, 73, 74, 75, 76, 77, 78, 79]`

## Exact local source structures

### `frontend/src/services/partsClient.ts`

- SHA-256: `06b5d486f6afd7b68c86570f47e6234a7ffdb8ae054e28ccda330f847e0a659f`
- Git blob: `b00d3dae7dee79eeced5e15e9ef706ed049fe88e`
- Lines: 266
- Patch 259 exact adjacency anchor count: 0
- `stock_status` line(s): [122]
- `limit` setter line(s): [126, 162, 204, 236]
- `offset` setter line(s): [130, 240]

#### Exact local `getParts` region — lines 69-142

```tsx
 69 |   }
 70 |
 71 |   return response.json() as Promise<T>;
 72 | }
 73 |
 74 |
 75 | export function createPart(
 76 |   token: string,
 77 |   payload: CreatePartPayload
 78 | ): Promise<Part> {
 79 |   return requestJson<Part>("/parts", token, {
 80 |     method: "POST",
 81 |     body: JSON.stringify(payload)
 82 |   });
 83 | }
 84 |
 85 |
 86 | // PATCH 169: Stored Parts location filter client
 87 | export function getParts(
 88 |   token: string,
 89 |   options?: {
 90 |     partTypeId?: number;
 91 |     locationId?: number;
 92 |     search?: string;
 93 |     stockStatus?: PartStockStatus;
 94 |     limit?: number;
 95 |     offset?: number;
 96 |   }
 97 | ): Promise<PartCollection> {
 98 |   const parameters = new URLSearchParams();
 99 |
100 |   if (options?.partTypeId) {
101 |     parameters.set(
102 |       "part_type_id",
103 |       String(options.partTypeId)
104 |     );
105 |   }
106 |
107 |   if (options?.locationId) {
108 |     parameters.set(
109 |       "location_id",
110 |       String(options.locationId)
111 |     );
112 |   }
113 |
114 |   // PATCH 217: typed backend universal-search option
115 |   const search = options?.search?.trim();
116 |   if (search) {
117 |     parameters.set("search", search);
118 |   }
119 |
120 |   // PATCH 232: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
121 |   if (options?.stockStatus) {
122 |     parameters.set("stock_status", options.stockStatus);
123 |   }
124 |
125 |   if (options?.limit !== undefined) {
126 |     parameters.set("limit", String(options.limit));
127 |   }
128 |
129 |   if (options?.offset !== undefined) {
130 |     parameters.set("offset", String(options.offset));
131 |   }
132 |
133 |   const query = parameters.toString();
134 |
135 |   return requestJson<PartCollection>(
136 |     `/parts${query ? `?${query}` : ""}`,
137 |     token
138 |   );
139 | }
140 |
141 |
142 | // PATCH 186: dashboard low-stock summary client
```

### `frontend/src/types/parts.ts`

- SHA-256: `6c6cfe34556875be7363c0d5ffb12f798fe9deb8b1c70a509265a8ce21080123`
- Git blob: `284fdb85da239272da15139112d7591a3e1c00dd`
- Lines: 159

#### Part stock-status type and neighbours — lines 63-97

```tsx
63 |   field_values: PartFieldValue[];
64 | }
65 |
66 | // PATCH 232: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
67 | export type PartStockStatus =
68 |   | "all"
69 |   | "in"
70 |   | "low"
71 |   | "out";
72 |
73 | export interface PartCollection {
74 |   total: number;
75 |   limit: number;
76 |   offset: number;
77 |   parts: Part[];
78 | }
79 |
80 |
81 | // PATCH 186: dashboard low-stock summary contract
82 | export interface LowStockSummary {
83 |   total: number;
84 |   low_stock_count: number;
85 |   out_of_stock_count: number;
86 |   limit: number;
87 |   parts: Part[];
88 | }
89 |
90 | // PATCH 153: recoverable part deletion and restoration types
91 | export interface DeletedPart extends Part {
92 |   is_deleted: true;
93 |   deleted_at: string;
94 | }
95 |
96 | export interface DeletedPartCollection {
97 |   total: number;
```

### `backend/app/api/routes/parts.py`

- SHA-256: `565edd0a5e09b410e868308f5ffa43a3bc737292786051869a3ed25a457423b1`
- Git blob: `80e19dbaf30435cfd7c5ed7f821ab8a09a626d08`
- Lines: 299
- Parts route function: `read_parts` lines 44-66

#### Parts list route — lines 44-66

```python
44 | def read_parts(
45 |     part_type_id: int | None = Query(default=None, gt=0),
46 |     location_id: int | None = Query(default=None, gt=0),
47 |     search: str | None = Query(default=None, max_length=180),
48 |     # PATCH 229: PARTPILOT_STORED_PARTS_STOCK_FILTER_V229
49 |     stock_status: Literal["all", "in", "low", "out"] = Query(
50 |         default="all"
51 |     ),
52 |     limit: int = Query(default=100, ge=1, le=250),
53 |     offset: int = Query(default=0, ge=0),
54 |     current_user=Depends(get_current_user),
55 |     db: Session = Depends(get_db),
56 | ) -> PartCollectionResponse:
57 |     del current_user
58 |     return list_parts(
59 |         db,
60 |         part_type_id=part_type_id,
61 |         location_id=location_id,
62 |         search=search,
63 |         stock_status=stock_status,
64 |         limit=limit,
65 |         offset=offset,
66 |     )
```

### `backend/app/services/parts.py`

- SHA-256: `3c7c0d61105cdfe9200a11f92eca90588b9487dbcef316578791b1cdca53e27b`
- Git blob: `3232d936c49ca047263c8a0404dceccf00fed73f`
- Lines: 1455
- Top-level functions: _has_submitted_value@59-64, _validate_url@67-72, _validate_and_build_field_value@75-169, _serialize_part@173-269, create_part@272-450, get_part@453-457, _normalise_part_search@461-465, _searchable_text@468-472, _part_search_condition@475-558, _part_search_order@561-579, _part_stock_conditions@586-617, list_parts@620-680, list_low_stock_parts@684-752, _part_metadata_snapshot@758-797, update_part_metadata@800-993, _adjustment_delta@1012-1017, _serialize_stock_movement@1020-1037, adjust_part_quantity@1040-1150, list_part_movements@1153-1185, _serialize_deleted_part@1188-1200, _part_lifecycle_snapshot@1203-1243, list_deleted_parts@1246-1279, soft_delete_part@1282-1360, restore_part@1363-1455
- Patch 260 exact helper-insertion anchor count: 0
- `available_quantity =` line(s): [230, 564, 592]
- `order_by =` line(s): [647]
- `_part_search_order(` line(s): [561, 648]
- `query.order_by` line(s): []

#### Function `_part_search_order` — lines 561-579

```python
561 | def _part_search_order(term: str):
562 |     part_number = func.lower(func.coalesce(Part.part_number, ""))
563 |     name = func.lower(func.coalesce(Part.name, ""))
564 |     available_quantity = Part.total_quantity - Part.reserved_quantity
565 |     return (
566 |         case((available_quantity > 0, 0), else_=1).asc(),
567 |         case((part_number == term, 0), else_=1).asc(),
568 |         case(
569 |             (part_number.startswith(term, autoescape=True), 0),
570 |             else_=1,
571 |         ).asc(),
572 |         case((name == term, 0), else_=1).asc(),
573 |         case(
574 |             (name.startswith(term, autoescape=True), 0),
575 |             else_=1,
576 |         ).asc(),
577 |         Part.updated_at.desc(),
578 |         Part.id.desc(),
579 |     )
```
#### Function `list_parts` — lines 620-680

```python
620 | def list_parts(
621 |     db: Session,
622 |     *,
623 |     part_type_id: int | None = None,
624 |     location_id: int | None = None,
625 |     search: str | None = None,
626 |     stock_status: str = "all",
627 |     limit: int = 100,
628 |     offset: int = 0,
629 | ) -> PartCollectionResponse:
630 |     conditions = [Part.is_deleted.is_(False)]
631 |     if part_type_id is not None:
632 |         conditions.append(Part.part_type_id == part_type_id)
633 |     if location_id is not None:
634 |         conditions.append(Part.location_id == location_id)
635 |     conditions.extend(_part_stock_conditions(stock_status))
636 |
637 |     search_term = _normalise_part_search(search)
638 |     if search_term is not None:
639 |         conditions.append(_part_search_condition(search_term))
640 |
641 |     total = int(
642 |         db.execute(
643 |             select(func.count(Part.id)).where(*conditions)
644 |         ).scalar_one()
645 |     )
646 |
647 |     order_by = (
648 |         _part_search_order(search_term)
649 |         if search_term is not None
650 |         else (
651 |             case(
652 |                 (
653 |                     (
654 |                         Part.total_quantity
655 |                         - Part.reserved_quantity
656 |                     )
657 |                     > 0,
658 |                     0,
659 |                 ),
660 |                 else_=1,
661 |             ).asc(),
662 |             Part.created_at.desc(),
663 |             Part.id.desc(),
664 |         )
665 |     )
666 |     parts = list(
667 |         db.execute(
668 |             select(Part)
669 |             .where(*conditions)
670 |             .order_by(*order_by)
671 |             .limit(limit)
672 |             .offset(offset)
673 |         ).scalars()
674 |     )
675 |     return PartCollectionResponse(
676 |         total=total,
677 |         limit=limit,
678 |         offset=offset,
679 |         parts=[_serialize_part(db, part) for part in parts],
680 |     )
```

### `backend/app/db/smoke_test.py`

- SHA-256: `5584f5008536cf82fa4075fc73e0df92f525a8f1de2dc82257b9f7bdc8f9a115`
- Git blob: `66f9d084c8f0c88a25d8da0eb07a87a9b785b5bf`
- Lines: 6756

#### Universal-search response helper — lines 6300-6394

```python
6300 |                 "Universal search route should require authentication, got "
6301 |                 f"{unauthenticated.status_code}: {unauthenticated.text}"
6302 |             )
6303 |
6304 |         def response_for(
6305 |             search: str,
6306 |             *,
6307 |             limit: int = 100,
6308 |             offset: int = 0,
6309 |             selected_type_id: int | None = None,
6310 |             selected_location_id: int | None = None,
6311 |             stock_status: str = "all",
6312 |         ):
6313 |             params: dict[str, str | int] = {
6314 |                 "search": search,
6315 |                 "stock_status": stock_status,
6316 |                 "limit": limit,
6317 |                 "offset": offset,
6318 |             }
6319 |             if selected_type_id is not None:
6320 |                 params["part_type_id"] = selected_type_id
6321 |             if selected_location_id is not None:
6322 |                 params["location_id"] = selected_location_id
6323 |             response = client.get(
6324 |                 "/api/parts",
6325 |                 params=params,
6326 |                 headers=headers,
6327 |             )
6328 |             if response.status_code != 200:
6329 |                 fail(
6330 |                     f"Universal search failed for {search!r}: "
6331 |                     f"{response.status_code} {response.text}"
6332 |                 )
6333 |             payload = response.json()
6334 |             returned_ids = [
6335 |                 item.get("id")
6336 |                 for item in payload.get("parts", [])
6337 |             ]
6338 |             if len(returned_ids) != len(set(returned_ids)):
6339 |                 fail(
6340 |                     f"Universal search returned duplicate rows for "
6341 |                     f"{search!r}: {returned_ids}"
6342 |                 )
6343 |             if payload.get("limit") != limit:
6344 |                 fail(
6345 |                     f"Universal search returned the wrong limit for "
6346 |                     f"{search!r}: {payload}"
6347 |                 )
6348 |             if payload.get("offset") != offset:
6349 |                 fail(
6350 |                     f"Universal search returned the wrong offset for "
6351 |                     f"{search!r}: {payload}"
6352 |                 )
6353 |             return payload, returned_ids
6354 |
6355 |         exact_checks = (
6356 |             (f"{suffix}-irfz44n", ids["core"], "part number"),
6357 |             (f"avalanche mosfet {suffix}".upper(), ids["core"], "name"),
6358 |             (description_token.upper(), ids["core"], "description"),
6359 |             (package_token.upper(), ids["core"], "package"),
6360 |             (notes_token.upper(), ids["core"], "notes"),
6361 |             (manufacturer_name.upper(), ids["core"], "manufacturer"),
6362 |             (alias_token.upper(), ids["alias"], "alias"),
6363 |             (text_token.upper(), ids["text"], "custom text value"),
6364 |             (numeric_token, ids["number"], "custom numeric value"),
6365 |             (wildcard_token, ids["core"], "literal SQL wildcard text"),
6366 |         )
6367 |         for query, expected_id, label in exact_checks:
6368 |             payload, returned_ids = response_for(
6369 |                 query,
6370 |                 selected_type_id=type_id,
6371 |             )
6372 |             if payload.get("total") != 1 or returned_ids != [expected_id]:
6373 |                 fail(
6374 |                     f"Universal search {label} coverage is incorrect for "
6375 |                     f"{query!r}: {payload}"
6376 |                 )
6377 |
6378 |         location_search_payload, location_search_ids = response_for(
6379 |             location_name.upper(),
6380 |             selected_type_id=type_id,
6381 |         )
6382 |         expected_location_search_ids = {
6383 |             ids["core"],
6384 |             ids["shared_available"],
6385 |             ids["shared_out"],
6386 |         }
6387 |         if (
6388 |             location_search_payload.get("total") != 3
6389 |             or set(location_search_ids) != expected_location_search_ids
6390 |             or location_search_ids[-1] != ids["shared_out"]
6391 |             or ids["shared_available_unassigned"] in location_search_ids
6392 |             or ids["deleted"] in location_search_ids
6393 |         ):
6394 |             fail(
```
#### Invalid stock-status test — lines 6636-6706

```python
6636 |         out_payload, out_ids = response_for(
6637 |             shared_token,
6638 |             selected_type_id=type_id,
6639 |             stock_status="out",
6640 |         )
6641 |         if (
6642 |             out_payload.get("total") != 1
6643 |             or out_ids != [ids["shared_out"]]
6644 |         ):
6645 |             fail(
6646 |                 "Universal search out-of-stock filtering is incorrect: "
6647 |                 f"{out_payload}"
6648 |             )
6649 |
6650 |         combined_payload, combined_ids = response_for(
6651 |             shared_token,
6652 |             selected_type_id=type_id,
6653 |             selected_location_id=location_id,
6654 |             stock_status="low",
6655 |         )
6656 |         if (
6657 |             combined_payload.get("total") != 1
6658 |             or combined_ids != [ids["shared_available"]]
6659 |         ):
6660 |             fail(
6661 |                 "Universal search stock, type, and location "
6662 |                 "composition is incorrect: "
6663 |                 f"{combined_payload}"
6664 |             )
6665 |
6666 |         invalid_stock_status = client.get(
6667 |             "/api/parts",
6668 |             params={
6669 |                 "part_type_id": type_id,
6670 |                 "stock_status": "missing",
6671 |             },
6672 |             headers=headers,
6673 |         )
6674 |         if invalid_stock_status.status_code != 422:
6675 |             fail(
6676 |                 "Invalid stock_status should return 422, got "
6677 |                 f"{invalid_stock_status.status_code}: "
6678 |                 f"{invalid_stock_status.text}"
6679 |             )
6680 |
6681 |         empty_payload, empty_ids = response_for(
6682 |             f"no-match-{suffix}-absent",
6683 |             selected_type_id=type_id,
6684 |         )
6685 |         if empty_payload.get("total") != 0 or empty_ids != []:
6686 |             fail(
6687 |                 "Universal search empty result is incorrect: "
6688 |                 f"{empty_payload}"
6689 |             )
6690 |
6691 |         invalid_length = client.get(
6692 |             "/api/parts",
6693 |             params={
6694 |                 "search": "x" * 181,
6695 |                 "part_type_id": type_id,
6696 |             },
6697 |             headers=headers,
6698 |         )
6699 |         if invalid_length.status_code != 422:
6700 |             fail(
6701 |                 "Universal search terms longer than 180 characters should "
6702 |                 f"return 422, got {invalid_length.status_code}: "
6703 |                 f"{invalid_length.text}"
6704 |             )
6705 |
6706 |     finally:
```
#### Universal-search PASS message — lines 6705-6725

```python
6705 |
6706 |     finally:
6707 |         cleanup()
6708 |
6709 |     ok(
6710 |         "Protected universal part search covers metadata, type, manufacturer, "
6711 |         "location, aliases, tags, custom text/numeric/boolean values and "
6712 |         "field labels; preserves type, location, and stock-status filters, "
6713 |         "totals, pagination, literal wildcards, case-insensitive partial "
6714 |         "matching, duplicate suppression, deleted exclusion, and "
6715 |         "available-first deterministic ordering"
6716 |     )
6717 |
6718 | def main() -> None:
6719 |     checks = [
6720 |         check_db_connects,
6721 |         check_sqlite_foreign_keys,
6722 |         check_alembic_at_head,
6723 |         check_seed_data,
6724 |         check_invalid_part_rejected,
6725 |         check_valid_part_insert_rolls_back,
```

### `frontend/src/pages/PartManager.tsx`

- SHA-256: `5aaf01b22a7a1a84e2a5bdc87cf9da4dda6840889cf532cc5911e35b62a9a4aa`
- Git blob: `24f2f4357f2676ccf2869301a90abc8d6728e0b8`
- Lines: 3187
- Section copy counts: {"Available subtitle": 1, "Separate results": 1, "Stocked results": 1}
- Inventory state lines: ["404:const [inventoryLoading, setInventoryLoading] = useState(true);", "410:const [inventoryQuery, setInventoryQuery] = useState(\"\");", "414:useState<InventoryStockFilter>(\"all\");", "419:useState<InventoryPageSize>(readInventoryPageSizePreference);", "420:const [inventoryOffset, setInventoryOffset] = useState(0);"]

#### Stored Parts request — lines 583-653

```tsx
583 |     return () => {
584 |       window.clearTimeout(timeoutId);
585 |     };
586 |   }, [inventoryQuery]);
587 |
588 |   // PATCH 233: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
589 |   useEffect(() => {
590 |     if (!token) {
591 |       inventoryRequestSequence.current += 1;
592 |       setInventoryCollection(null);
593 |       setInventoryLoading(false);
594 |       return;
595 |     }
596 |
597 |     const requestId = inventoryRequestSequence.current + 1;
598 |     inventoryRequestSequence.current = requestId;
599 |     let cancelled = false;
600 |
601 |     setInventoryLoading(true);
602 |     setInventoryError(null);
603 |     getParts(token, {
604 |       partTypeId: inventoryPartTypeFilter ?? undefined,
605 |       locationId: inventoryLocationFilter ?? undefined,
606 |       search: inventoryServerSearch || undefined,
607 |       stockStatus: inventoryStockFilter,
608 |       limit: inventoryPageSize,
609 |       offset: inventoryOffset
610 |     })
611 |       .then((result) => {
612 |         if (
613 |           !cancelled
614 |           && requestId === inventoryRequestSequence.current
615 |         ) {
616 |           const lastValidOffset = result.total > 0
617 |             ? Math.floor((result.total - 1) / inventoryPageSize)
618 |               * inventoryPageSize
619 |             : 0;
620 |
621 |           if (inventoryOffset > lastValidOffset) {
622 |             setInventoryOffset(lastValidOffset);
623 |             return;
624 |           }
625 |
626 |           setInventoryCollection(result);
627 |         }
628 |       })
629 |       .catch((caught) => {
630 |         if (
631 |           !cancelled
632 |           && requestId === inventoryRequestSequence.current
633 |         ) {
634 |           setInventoryError(
635 |             caught instanceof Error
636 |               ? caught.message
637 |               : "Unable to load inventory"
638 |           );
639 |         }
640 |       })
641 |       .finally(() => {
642 |         if (
643 |           !cancelled
644 |           && requestId === inventoryRequestSequence.current
645 |         ) {
646 |           setInventoryLoading(false);
647 |         }
648 |       });
649 |
650 |     return () => {
651 |       cancelled = true;
652 |     };
653 |   }, [
```
#### Inventory state near stock filter — lines 395-463

```tsx
395 | }: PartManagerProps) {
396 |   const { token } = useAuth();
397 |   const [collection, setCollection] = useState<PartTypeCollection | null>(null);
398 |   const [selectedId, setSelectedId] = useState<number | null>(null);
399 |   const [filter, setFilter] = useState<FilterMode>("all");
400 |   const [query, setQuery] = useState("");
401 |   // PATCH 110: inventory collection state
402 |   const [inventoryCollection, setInventoryCollection] =
403 |     useState<PartCollection | null>(null);
404 |   const [inventoryLoading, setInventoryLoading] = useState(true);
405 |   const [inventoryError, setInventoryError] =
406 |     useState<string | null>(null);
407 |   const [inventoryRefreshSequence, setInventoryRefreshSequence] =
408 |     useState(0);
409 |   // PATCH 232: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
410 |   const [inventoryQuery, setInventoryQuery] = useState("");
411 |   const [inventoryServerSearch, setInventoryServerSearch] =
412 |     useState("");
413 |   const [inventoryStockFilter, setInventoryStockFilter] =
414 |     useState<InventoryStockFilter>("all");
415 |   // PATCH 240: PARTPILOT_STORED_PARTS_PAGINATION_V240
416 |   const [inventoryPartTypeFilter, setInventoryPartTypeFilter] =
417 |     useState<number | null>(null);
418 |   const [inventoryPageSize, setInventoryPageSize] =
419 |     useState<InventoryPageSize>(readInventoryPageSizePreference);
420 |   const [inventoryOffset, setInventoryOffset] = useState(0);
421 |   const inventoryRequestSequence = useRef(0);
422 |   // PATCH 194: settings-driven out-of-stock grouping
423 |   const [showOutOfStockSection, setShowOutOfStockSection] =
424 |     useState(true);
425 |   const [
426 |     inventorySearchSettingsError,
427 |     setInventorySearchSettingsError
428 |   ] = useState<string | null>(null);
429 |   // PATCH 171: Stored Parts location display and filtering
430 |   const [inventoryLocations, setInventoryLocations] =
431 |     useState<LocationOption[]>([]);
432 |   const [inventoryLocationsLoading, setInventoryLocationsLoading] =
433 |     useState(true);
434 |   const [inventoryLocationsError, setInventoryLocationsError] =
435 |     useState<string | null>(null);
436 |   const [inventoryLocationFilter, setInventoryLocationFilter] =
437 |     useState<number | null>(null);
438 |   // PATCH 124: selected inventory record and drawer state
439 |   const [selectedInventoryPartId, setSelectedInventoryPartId] =
440 |     useState<number | null>(null);
441 |   const [selectedInventoryPart, setSelectedInventoryPart] =
442 |     useState<Part | null>(null);
443 |   const [partDetailsLoading, setPartDetailsLoading] = useState(false);
444 |   const [partDetailsError, setPartDetailsError] =
445 |     useState<string | null>(null);
446 |   const [partMovements, setPartMovements] = useState<StockMovement[]>([]);
447 |   const [partMovementsLoading, setPartMovementsLoading] = useState(false);
448 |   const [partMovementsError, setPartMovementsError] =
449 |     useState<string | null>(null);
450 |   const [adjustmentOperation, setAdjustmentOperation] =
451 |     useState<QuantityAdjustmentOperation>("add");
452 |   const [adjustmentQuantity, setAdjustmentQuantity] = useState("");
453 |   const [adjustmentReason, setAdjustmentReason] = useState("");
454 |   const [adjustmentNote, setAdjustmentNote] = useState("");
455 |   const [adjustmentSaving, setAdjustmentSaving] = useState(false);
456 |   const [adjustmentError, setAdjustmentError] =
457 |     useState<string | null>(null);
458 |   const [adjustmentSuccess, setAdjustmentSuccess] =
459 |     useState<string | null>(null);
460 |   const [isLoading, setIsLoading] = useState(true);
461 |   const [error, setError] = useState<string | null>(null);
462 |
463 |   const [isCreating, setIsCreating] = useState(false);
```
#### Current inventory table renderer — lines 1456-1623

```tsx
1456 |   }
1457 |
1458 |   function renderInventoryTable(
1459 |     parts: Part[],
1460 |     labelledBy?: string
1461 |   ) {
1462 |     return (
1463 |       <div className="inventory-table-wrap">
1464 |         <table
1465 |           className="inventory-table"
1466 |           aria-labelledby={labelledBy}
1467 |         >
1468 |           <thead>
1469 |             <tr>
1470 |               <th scope="col">Part</th>
1471 |               <th scope="col">Type</th>
1472 |               <th scope="col">Manufacturer</th>
1473 |               <th scope="col">Location</th>
1474 |               <th scope="col">Available</th>
1475 |               <th scope="col">Total</th>
1476 |               <th scope="col">Status</th>
1477 |             </tr>
1478 |           </thead>
1479 |           <tbody>
1480 |             {parts.map((part) => (
1481 |               <tr
1482 |                 key={part.id}
1483 |                 className={
1484 |                   selectedInventoryPartId === part.id
1485 |                     ? "inventory-row-action is-selected"
1486 |                     : "inventory-row-action"
1487 |                 }
1488 |                 tabIndex={0}
1489 |                 aria-label={`View details for ${inventoryPartName(part)}`}
1490 |                 aria-haspopup="dialog"
1491 |                 onClick={() => openPartDetails(part.id)}
1492 |                 onKeyDown={(event) => {
1493 |                   if (
1494 |                     event.key === "Enter"
1495 |                     || event.key === " "
1496 |                   ) {
1497 |                     event.preventDefault();
1498 |                     openPartDetails(part.id);
1499 |                   }
1500 |                 }}
1501 |               >
1502 |                 <td>
1503 |                   <strong>{inventoryPartName(part)}</strong>
1504 |                   <small>
1505 |                     {part.part_number || "No part number"}
1506 |                   </small>
1507 |                 </td>
1508 |                 <td>{part.part_type_name}</td>
1509 |                 <td>
1510 |                   {part.manufacturer_name || "Not specified"}
1511 |                 </td>
1512 |                 <td
1513 |                   className="inventory-location-cell"
1514 |                   title={part.location_name || "Not specified"}
1515 |                 >
1516 |                   {part.location_name || "Not specified"}
1517 |                 </td>
1518 |                 <td className="inventory-quantity">
1519 |                   {part.available_quantity}
1520 |                 </td>
1521 |                 <td className="inventory-quantity">
1522 |                   {part.total_quantity}
1523 |                 </td>
1524 |                 <td>
1525 |                   <span
1526 |                     className={
1527 |                       `inventory-stock-pill ${
1528 |                         inventoryStockClass(part)
1529 |                       }`
1530 |                     }
1531 |                   >
1532 |                     {inventoryStockLabel(part)}
1533 |                   </span>
1534 |                 </td>
1535 |               </tr>
1536 |             ))}
1537 |           </tbody>
1538 |         </table>
1539 |       </div>
1540 |     );
1541 |   }
1542 |
1543 |   return (
1544 |     <div
1545 |       className={
1546 |         `page-stack part-manager-page${
1547 |           inventoryOnly ? " inventory-page" : ""
1548 |         }`
1549 |       }
1550 |       data-inventory-page-mode={
1551 |         inventoryOnly ? "inventory-page-mode-v202" : undefined
1552 |       }
1553 |       data-manufacturer-preset-version="part-manager-manufacturer-preset-v106"
1554 |       data-part-lifecycle-version="part-lifecycle-v153"
1555 |       data-out-of-stock-grouping-version="stored-parts-out-of-stock-group-v194"
1556 |     >
1557 |       {inventoryOnly ? (
1558 |         <header
1559 |           className="page-header part-manager-header inventory-page-header"
1560 |           data-inventory-page-version="inventory-live-page-v202"
1561 |         >
1562 |           <div>
1563 |             <p className="eyebrow">Inventory</p>
1564 |             <h1>Stored parts</h1>
1565 |             <p>
1566 |               Search, filter, inspect, add, edit, adjust, delete, and restore
1567 |               the components kept in this Part Pilot installation.
1568 |             </p>
1569 |           </div>
1570 |           <span className="status-pill">
1571 |             {isLoading
1572 |               ? "Loading templates"
1573 |               : collection
1574 |                 ? `${collection.total} part types`
1575 |                 : "Inventory workspace"}
1576 |           </span>
1577 |         </header>
1578 |       ) : (
1579 |               <header className="page-header part-manager-header">
1580 |                 <div>
1581 |                   <p className="eyebrow">Phase 4</p>
1582 |                   <h1>Part Manager</h1>
1583 |                   <p>
1584 |                     Browse built-in electronics templates and create custom part
1585 |                     types for the inventory you actually keep.
1586 |                   </p>
1587 |                 </div>
1588 |                 <div className="part-manager-header-actions">
1589 |                   <span className="status-pill">
1590 |                     {isCreating
1591 |                       ? editingTypeId === null
1592 |                         ? "Creating custom type"
1593 |                         : "Editing custom type"
1594 |                       : "Template manager"}
1595 |                   </span>
1596 |
1597 |                   <button
1598 |                     className="part-manager-create-button"
1599 |                     type="button"
1600 |                     onClick={isCreating ? closeCreator : openCreator}
1601 |                     disabled={isSaving}
1602 |                   >
1603 |                     {isCreating ? "Close creator" : "New custom type"}
1604 |                   </button>
1605 |                 </div>
1606 |               </header>
1607 |       )}
1608 |
1609 |       {!inventoryOnly && collection ? (
1610 |         <section className="part-manager-stats" aria-label="Part type totals">
1611 |           <article className="card">
1612 |             <span>Part types</span>
1613 |             <strong>{collection.total}</strong>
1614 |           </article>
1615 |           <article className="card">
1616 |             <span>Built-in</span>
1617 |             <strong>{collection.builtin_count}</strong>
1618 |           </article>
1619 |           <article className="card">
1620 |             <span>Custom</span>
1621 |             <strong>{collection.custom_count}</strong>
1622 |           </article>
1623 |           <article className="card">
```
#### Current Available section — lines 2516-2601

```tsx
2516 |               <button
2517 |                 type="button"
2518 |                 onClick={() => {
2519 |                   setInventoryQuery("");
2520 |                   setInventoryStockFilter("all");
2521 |                   setInventoryPartTypeFilter(null);
2522 |                   setInventoryLocationFilter(null);
2523 |                   setInventoryOffset(0);
2524 |                 }}
2525 |               >
2526 |                 Clear filters
2527 |               </button>
2528 |             </div>
2529 |           ) : null}
2530 |
2531 |         {!inventoryLoading
2532 |           && !inventoryError
2533 |           && inventoryCollection
2534 |           && filteredInventoryParts.length > 0
2535 |           ? (
2536 |             <section
2537 |               className="inventory-available-section"
2538 |               data-available-card-version="stored-parts-available-card-v258"
2539 |               aria-labelledby="inventory-available-title"
2540 |             >
2541 |               <header className="inventory-available-header">
2542 |                 <div>
2543 |                   <p className="eyebrow">Stocked results</p>
2544 |                   <h3 id="inventory-available-title">
2545 |                     Available
2546 |                   </h3>
2547 |                   <p>
2548 |                     Matching parts with quantity ready to use.
2549 |                   </p>
2550 |                 </div>
2551 |                 <span>
2552 |                   {filteredInventoryParts.length}
2553 |                   {" "}
2554 |                   {filteredInventoryParts.length === 1
2555 |                     ? "part shown"
2556 |                     : "parts shown"}
2557 |                 </span>
2558 |               </header>
2559 |               {renderInventoryTable(
2560 |                 filteredInventoryParts,
2561 |                 "inventory-available-title"
2562 |               )}
2563 |             </section>
2564 |           )
2565 |           : null}
2566 |
2567 |         {!inventoryLoading
2568 |           && !inventoryError
2569 |           && inventoryCollection
2570 |           && outOfStockInventoryParts.length > 0 ? (
2571 |           <div
2572 |             className="inventory-results-separator"
2573 |             data-stock-separator-version="stored-parts-preference-v248"
2574 |             role="separator"
2575 |             aria-label="Out of stock results begin here"
2576 |           >
2577 |             <span className="inventory-results-separator-line" />
2578 |             <span className="inventory-results-separator-badge">
2579 |               Out of stock
2580 |             </span>
2581 |             <span className="inventory-results-separator-line" />
2582 |           </div>
2583 |         ) : null}
2584 |         {!inventoryLoading
2585 |           && !inventoryError
2586 |           && inventoryCollection
2587 |           && outOfStockInventoryParts.length > 0 ? (
2588 |             <section
2589 |               className="inventory-out-of-stock-section"
2590 |               data-out-of-stock-grouping-version="stored-parts-out-of-stock-group-v194"
2591 |               aria-labelledby="inventory-out-of-stock-title"
2592 |             >
2593 |               <header className="inventory-out-of-stock-header">
2594 |                 <div>
2595 |                   <p className="eyebrow">Separate results</p>
2596 |                   <h3 id="inventory-out-of-stock-title">
2597 |                     Out of stock
2598 |                   </h3>
2599 |                   <p>
2600 |                     These matching parts have no available quantity.
2601 |                   </p>
```
#### Current Out of stock section — lines 2568-2653

```tsx
2568 |           && !inventoryError
2569 |           && inventoryCollection
2570 |           && outOfStockInventoryParts.length > 0 ? (
2571 |           <div
2572 |             className="inventory-results-separator"
2573 |             data-stock-separator-version="stored-parts-preference-v248"
2574 |             role="separator"
2575 |             aria-label="Out of stock results begin here"
2576 |           >
2577 |             <span className="inventory-results-separator-line" />
2578 |             <span className="inventory-results-separator-badge">
2579 |               Out of stock
2580 |             </span>
2581 |             <span className="inventory-results-separator-line" />
2582 |           </div>
2583 |         ) : null}
2584 |         {!inventoryLoading
2585 |           && !inventoryError
2586 |           && inventoryCollection
2587 |           && outOfStockInventoryParts.length > 0 ? (
2588 |             <section
2589 |               className="inventory-out-of-stock-section"
2590 |               data-out-of-stock-grouping-version="stored-parts-out-of-stock-group-v194"
2591 |               aria-labelledby="inventory-out-of-stock-title"
2592 |             >
2593 |               <header className="inventory-out-of-stock-header">
2594 |                 <div>
2595 |                   <p className="eyebrow">Separate results</p>
2596 |                   <h3 id="inventory-out-of-stock-title">
2597 |                     Out of stock
2598 |                   </h3>
2599 |                   <p>
2600 |                     These matching parts have no available quantity.
2601 |                   </p>
2602 |                 </div>
2603 |                 <span>
2604 |                   {outOfStockInventoryParts.length}
2605 |                   {" "}
2606 |                   {outOfStockInventoryParts.length === 1
2607 |                     ? "part"
2608 |                     : "parts"}
2609 |                 </span>
2610 |               </header>
2611 |               {renderInventoryTable(
2612 |                 outOfStockInventoryParts,
2613 |                 "inventory-out-of-stock-title"
2614 |               )}
2615 |             </section>
2616 |           ) : null}
2617 |
2618 |         {!inventoryLoading
2619 |           && !inventoryError
2620 |           && inventoryCollection
2621 |           && inventoryTotal > 0 ? (
2622 |             <nav
2623 |               className="inventory-pagination"
2624 |               data-pagination-version={
2625 |                 STORED_PARTS_PAGINATION_VERSION
2626 |               }
2627 |               aria-label="Stored parts pagination"
2628 |             >
2629 |               <div className="inventory-pagination-summary">
2630 |                 <strong>
2631 |                   Page {inventoryPageNumber} of {inventoryPageCount}
2632 |                 </strong>
2633 |                 <span>
2634 |                   Showing {inventoryRangeStart}–{inventoryRangeEnd} of
2635 |                   {" "}
2636 |                   {inventoryTotal}
2637 |                 </span>
2638 |               </div>
2639 |               <label className="inventory-page-size">
2640 |                 <span>Rows</span>
2641 |                 <select
2642 |                   value={inventoryPageSize}
2643 |                   data-page-size-preference-version={
2644 |                     STORED_PARTS_PREFERENCE_VERSION
2645 |                   }
2646 |                   onChange={(
2647 |                     event: ChangeEvent<HTMLSelectElement>
2648 |                   ) => {
2649 |                     setInventoryPageSize(
2650 |                       Number(event.target.value) as InventoryPageSize
2651 |                     );
2652 |                     setInventoryOffset(0);
2653 |                   }}
```

### `frontend/src/pages/PartManager.css`

- SHA-256: `26de80fbb88d30cfde437d3b2ade0a8c3092a6c885bee25cb12d4e400e5fc317`
- Git blob: `2b161d2548f6e861d3602d44011d81c432292a84`
- Lines: 3213
- `border-spacing` line(s): [2967, 3198]
- `box-shadow` line(s): [138, 473, 567, 770, 854, 1003, 1089, 1098, 1115, 1162, 1379, 1470, 1493, 1521, 1621, 1649, 1880, 1910, 2019, 2034, 2095, 2360, 2377, 2614, 2635, 2704, 2809, 2847, 2911]

#### Patch 257 CSS — lines 2839-2921

```css
2839 | /* END PATCH 248 */
2840 |
2841 | /* PATCH 257: STORED PARTS OUT-OF-STOCK CARD SEPARATION */
2842 | .part-manager-page .inventory-out-of-stock-section {
2843 |   --stored-parts-out-of-stock-card-v257: 1;
2844 |   border-color: rgba(248, 113, 113, 0.42) !important;
2845 |   border-left: 4px solid #ef4444 !important;
2846 |   background: rgba(69, 10, 10, 0.34) !important;
2847 |   box-shadow: none !important;
2848 | }
2849 |
2850 | .part-manager-page .inventory-out-of-stock-header {
2851 |   border-bottom-color: rgba(248, 113, 113, 0.3) !important;
2852 |   background: rgba(127, 29, 29, 0.28) !important;
2853 | }
2854 |
2855 | .part-manager-page .inventory-out-of-stock-header .eyebrow {
2856 |   color: #fca5a5 !important;
2857 | }
2858 |
2859 | .part-manager-page .inventory-out-of-stock-header h3 {
2860 |   color: #fee2e2 !important;
2861 | }
2862 |
2863 | .part-manager-page .inventory-out-of-stock-header p:last-child {
2864 |   color: #d6b4b4 !important;
2865 | }
2866 |
2867 | .part-manager-page .inventory-out-of-stock-header > span {
2868 |   border-color: rgba(248, 113, 113, 0.46) !important;
2869 |   background: rgba(239, 68, 68, 0.18) !important;
2870 |   color: #fecaca !important;
2871 | }
2872 |
2873 | .part-manager-page .inventory-out-of-stock-section .inventory-table-wrap {
2874 |   background: rgba(69, 10, 10, 0.14) !important;
2875 | }
2876 |
2877 | .part-manager-page .inventory-out-of-stock-section .inventory-table th {
2878 |   border-bottom-color: rgba(248, 113, 113, 0.24) !important;
2879 |   background: rgba(127, 29, 29, 0.24) !important;
2880 |   color: #e8b7b7 !important;
2881 | }
2882 |
2883 | .part-manager-page .inventory-out-of-stock-section .inventory-table td {
2884 |   border-bottom-color: rgba(248, 113, 113, 0.15) !important;
2885 | }
2886 |
2887 | .part-manager-page
2888 |   .inventory-out-of-stock-section
2889 |   .inventory-table
2890 |   tbody
2891 |   tr:hover
2892 |   td {
2893 |   background: rgba(127, 29, 29, 0.16) !important;
2894 | }
2895 | /* END PATCH 257 */
2896 |
2897 | /* PATCH 258: STORED PARTS AVAILABLE CARD AND ROW POLISH */
2898 | .part-manager-page {
2899 |   --stored-parts-row-polish-v258: 1;
2900 | }
2901 |
2902 | .part-manager-page .inventory-available-section {
2903 |   display: grid !important;
2904 |   gap: 0 !important;
2905 |   margin: 0 !important;
2906 |   overflow: hidden !important;
2907 |   border: 1px solid rgba(45, 212, 191, 0.34) !important;
2908 |   border-left: 4px solid #14b8a6 !important;
2909 |   border-radius: 9px !important;
2910 |   background: rgba(4, 47, 46, 0.3) !important;
2911 |   box-shadow: none !important;
2912 | }
2913 |
2914 | .part-manager-page .inventory-available-header {
2915 |   display: flex !important;
2916 |   align-items: flex-start !important;
2917 |   justify-content: space-between !important;
2918 |   gap: 18px !important;
2919 |   padding: 14px 16px !important;
2920 |   border-bottom: 1px solid rgba(45, 212, 191, 0.24) !important;
2921 |   background: rgba(13, 148, 136, 0.15) !important;
```
#### Patch 258 CSS — lines 2895-2977

```css
2895 | /* END PATCH 257 */
2896 |
2897 | /* PATCH 258: STORED PARTS AVAILABLE CARD AND ROW POLISH */
2898 | .part-manager-page {
2899 |   --stored-parts-row-polish-v258: 1;
2900 | }
2901 |
2902 | .part-manager-page .inventory-available-section {
2903 |   display: grid !important;
2904 |   gap: 0 !important;
2905 |   margin: 0 !important;
2906 |   overflow: hidden !important;
2907 |   border: 1px solid rgba(45, 212, 191, 0.34) !important;
2908 |   border-left: 4px solid #14b8a6 !important;
2909 |   border-radius: 9px !important;
2910 |   background: rgba(4, 47, 46, 0.3) !important;
2911 |   box-shadow: none !important;
2912 | }
2913 |
2914 | .part-manager-page .inventory-available-header {
2915 |   display: flex !important;
2916 |   align-items: flex-start !important;
2917 |   justify-content: space-between !important;
2918 |   gap: 18px !important;
2919 |   padding: 14px 16px !important;
2920 |   border-bottom: 1px solid rgba(45, 212, 191, 0.24) !important;
2921 |   background: rgba(13, 148, 136, 0.15) !important;
2922 | }
2923 |
2924 | .part-manager-page .inventory-available-header h3,
2925 | .part-manager-page .inventory-available-header p {
2926 |   margin: 0 !important;
2927 | }
2928 |
2929 | .part-manager-page .inventory-available-header .eyebrow {
2930 |   color: #5eead4 !important;
2931 | }
2932 |
2933 | .part-manager-page .inventory-available-header h3 {
2934 |   margin-top: 3px !important;
2935 |   color: #ccfbf1 !important;
2936 |   font-size: 0.98rem !important;
2937 | }
2938 |
2939 | .part-manager-page .inventory-available-header p:last-child {
2940 |   margin-top: 5px !important;
2941 |   color: #9abbb8 !important;
2942 |   font-size: 0.73rem !important;
2943 | }
2944 |
2945 | .part-manager-page .inventory-available-header > span {
2946 |   flex: 0 0 auto !important;
2947 |   padding: 5px 8px !important;
2948 |   border: 1px solid rgba(94, 234, 212, 0.38) !important;
2949 |   border-radius: 999px !important;
2950 |   background: rgba(20, 184, 166, 0.15) !important;
2951 |   color: #99f6e4 !important;
2952 |   font-size: 0.68rem !important;
2953 |   font-weight: 800 !important;
2954 |   white-space: nowrap !important;
2955 | }
2956 |
2957 | .part-manager-page .inventory-available-section .inventory-table-wrap {
2958 |   border: 0 !important;
2959 |   border-radius: 0 !important;
2960 |   background: rgba(4, 47, 46, 0.11) !important;
2961 | }
2962 |
2963 | .part-manager-page
2964 |   :is(.inventory-available-section, .inventory-out-of-stock-section)
2965 |   .inventory-table {
2966 |   border-collapse: separate !important;
2967 |   border-spacing: 0 4px !important;
2968 |   padding: 0 6px 6px !important;
2969 | }
2970 |
2971 | .part-manager-page
2972 |   :is(.inventory-available-section, .inventory-out-of-stock-section)
2973 |   .inventory-table
2974 |   th {
2975 |   padding: 8px 12px !important;
2976 |   border-bottom: 0 !important;
2977 | }
```
#### Available header CSS — lines 2912-2994

```css
2912 | }
2913 |
2914 | .part-manager-page .inventory-available-header {
2915 |   display: flex !important;
2916 |   align-items: flex-start !important;
2917 |   justify-content: space-between !important;
2918 |   gap: 18px !important;
2919 |   padding: 14px 16px !important;
2920 |   border-bottom: 1px solid rgba(45, 212, 191, 0.24) !important;
2921 |   background: rgba(13, 148, 136, 0.15) !important;
2922 | }
2923 |
2924 | .part-manager-page .inventory-available-header h3,
2925 | .part-manager-page .inventory-available-header p {
2926 |   margin: 0 !important;
2927 | }
2928 |
2929 | .part-manager-page .inventory-available-header .eyebrow {
2930 |   color: #5eead4 !important;
2931 | }
2932 |
2933 | .part-manager-page .inventory-available-header h3 {
2934 |   margin-top: 3px !important;
2935 |   color: #ccfbf1 !important;
2936 |   font-size: 0.98rem !important;
2937 | }
2938 |
2939 | .part-manager-page .inventory-available-header p:last-child {
2940 |   margin-top: 5px !important;
2941 |   color: #9abbb8 !important;
2942 |   font-size: 0.73rem !important;
2943 | }
2944 |
2945 | .part-manager-page .inventory-available-header > span {
2946 |   flex: 0 0 auto !important;
2947 |   padding: 5px 8px !important;
2948 |   border: 1px solid rgba(94, 234, 212, 0.38) !important;
2949 |   border-radius: 999px !important;
2950 |   background: rgba(20, 184, 166, 0.15) !important;
2951 |   color: #99f6e4 !important;
2952 |   font-size: 0.68rem !important;
2953 |   font-weight: 800 !important;
2954 |   white-space: nowrap !important;
2955 | }
2956 |
2957 | .part-manager-page .inventory-available-section .inventory-table-wrap {
2958 |   border: 0 !important;
2959 |   border-radius: 0 !important;
2960 |   background: rgba(4, 47, 46, 0.11) !important;
2961 | }
2962 |
2963 | .part-manager-page
2964 |   :is(.inventory-available-section, .inventory-out-of-stock-section)
2965 |   .inventory-table {
2966 |   border-collapse: separate !important;
2967 |   border-spacing: 0 4px !important;
2968 |   padding: 0 6px 6px !important;
2969 | }
2970 |
2971 | .part-manager-page
2972 |   :is(.inventory-available-section, .inventory-out-of-stock-section)
2973 |   .inventory-table
2974 |   th {
2975 |   padding: 8px 12px !important;
2976 |   border-bottom: 0 !important;
2977 | }
2978 |
2979 | .part-manager-page
2980 |   :is(.inventory-available-section, .inventory-out-of-stock-section)
2981 |   .inventory-table
2982 |   tbody
2983 |   td {
2984 |   padding: 8px 12px !important;
2985 |   border-top: 1px solid rgba(148, 163, 184, 0.12) !important;
2986 |   border-bottom: 1px solid rgba(148, 163, 184, 0.12) !important;
2987 |   background: rgba(15, 23, 42, 0.52) !important;
2988 |   color: #cbd5e1 !important;
2989 |   transition:
2990 |     background-color 120ms ease,
2991 |     border-color 120ms ease !important;
2992 | }
2993 |
2994 | .part-manager-page
```
#### Out of stock header CSS — lines 2442-2524

```css
2442 | }
2443 |
2444 | .part-manager-page .inventory-out-of-stock-header {
2445 |   display: flex !important;
2446 |   align-items: flex-start !important;
2447 |   justify-content: space-between !important;
2448 |   gap: 18px !important;
2449 |   padding: 14px 16px !important;
2450 |   border-bottom: 1px solid rgba(239, 68, 68, 0.2) !important;
2451 |   background: rgba(127, 29, 29, 0.11) !important;
2452 | }
2453 |
2454 | .part-manager-page .inventory-out-of-stock-header h3,
2455 | .part-manager-page .inventory-out-of-stock-header p {
2456 |   margin: 0 !important;
2457 | }
2458 |
2459 | .part-manager-page .inventory-out-of-stock-header h3 {
2460 |   margin-top: 3px !important;
2461 |   color: #f8d4d4 !important;
2462 |   font-size: 0.98rem !important;
2463 | }
2464 |
2465 | .part-manager-page .inventory-out-of-stock-header p:last-child {
2466 |   margin-top: 5px !important;
2467 |   color: #b9a4aa !important;
2468 |   font-size: 0.73rem !important;
2469 | }
2470 |
2471 | .part-manager-page .inventory-out-of-stock-header > span {
2472 |   flex: 0 0 auto !important;
2473 |   padding: 5px 8px !important;
2474 |   border: 1px solid rgba(248, 113, 113, 0.3) !important;
2475 |   border-radius: 999px !important;
2476 |   background: rgba(239, 68, 68, 0.09) !important;
2477 |   color: #fca5a5 !important;
2478 |   font-size: 0.68rem !important;
2479 |   font-weight: 800 !important;
2480 |   white-space: nowrap !important;
2481 | }
2482 |
2483 | .part-manager-page .inventory-out-of-stock-section
2484 |   .inventory-table-wrap {
2485 |   border: 0 !important;
2486 |   border-radius: 0 !important;
2487 | }
2488 |
2489 | .part-manager-page .inventory-out-of-stock-section
2490 |   .inventory-table tbody tr:last-child td {
2491 |   border-bottom: 0 !important;
2492 | }
2493 |
2494 | .part-manager-page .inventory-settings-warning {
2495 |   margin: 0 16px 16px !important;
2496 |   padding: 9px 11px !important;
2497 |   border: 1px solid rgba(245, 158, 11, 0.28) !important;
2498 |   border-radius: 7px !important;
2499 |   background: rgba(120, 53, 15, 0.11) !important;
2500 |   color: #fcd34d !important;
2501 |   font-size: 0.72rem !important;
2502 | }
2503 |
2504 | @media (max-width: 760px) {
2505 |   .part-manager-page .inventory-out-of-stock-section {
2506 |     margin: 12px 0 0 !important;
2507 |   }
2508 |
2509 |   .part-manager-page .inventory-out-of-stock-header {
2510 |     align-items: stretch !important;
2511 |     flex-direction: column !important;
2512 |     gap: 10px !important;
2513 |     padding: 12px !important;
2514 |   }
2515 |
2516 |   .part-manager-page .inventory-out-of-stock-header > span {
2517 |     width: fit-content !important;
2518 |   }
2519 |
2520 |   .part-manager-page .inventory-settings-warning {
2521 |     margin: 0 10px 12px !important;
2522 |   }
2523 | }
2524 |
```

## Failure analysis

### Patch 259
- The parts-client transform required one exact adjacency between the existing
  `stock_status` block and the `limit` block.
- The actual local `getParts` region and old-anchor count are recorded above.

### Patch 260
- The service transform required one exact return block immediately followed by
  `def list_parts(`.
- The actual top-level function order, AST ranges, ordering statements and
  failed-anchor count are recorded above.

### Patches 261–264
- Patch 261 never executed because of Python f-string syntax.
- Patch 262 generated the report but source-excerpt blank lines contained
  trailing spaces; its rollback removed the report and restored memory.
- Patch 263 detected two deleted committed documentation files before writing.
- Patch 264 restored those files and left only the two pending app files changed.

## Safe implementation plan

1. Use this report as the source-shape authority while app source is pending.
2. Build service and route changes from the recorded Python AST function ranges,
   not raw whitespace or neighbouring text.
3. Scope client changes to the recorded `getParts` region and validate imports,
   options and query parameters independently.
4. Scope frontend changes to the recorded request state, pagination reset setter,
   request dependencies, table renderer and section header blocks.
5. Remove only “Stocked results”, “Separate results” and their subtitles.
6. Keep Available/Out of stock titles and counts and connect table headings to
   their section cards.
7. Add accessible server-backed sorting for Part, Type, Manufacturer, Location,
   Available, Total and Status across the full filtered result set.
8. Reset to page one on sort changes and preserve search, filters, stale guards,
   selection, quantity, history, edit, delete/restore and Available-first
   grouping under the All stock filter.
9. Add smoke tests using the exact local `response_for` and invalid-query shapes.
10. Validate every transformed file and reversal in memory before backup/write.
11. After automated and browser approval, checkpoint/commit/push promptly.

## Patch 265 write scope

The only created file is:

- `/projects/Part Pilot/fixes/logs/diagonostic_patch_265_stored_parts_sorting_local_source.md`

No tracked file, application source, database row, deployment, Git index entry,
commit or remote branch is changed.
