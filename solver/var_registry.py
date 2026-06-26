from collections import defaultdict


class VarRegistry:
    def __init__(self):
        self._entries = []
        self._index = defaultdict(lambda: defaultdict(set))

    def add(self, obj, references=(), **tags):
        idx = len(self._entries)
        self._entries.append({
            "value": obj,
            "tags": dict(tags),
            "references": list(references),
        })

        for dim, value in tags.items():
            self._index[dim][value].add(idx)

        return idx

    def _matches_tags(self, entry_tags, tags):
        for dim, expected in tags.items():
            if dim == "references":
                continue

            actual = entry_tags.get(dim)

            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
            else:
                if actual != expected:
                    return False

        return True
    def query_with_tags(self, **tags):
        if not tags:
            candidate_ids = set(range(len(self._entries)))
        else:
            candidate_ids = None

            for dim, value in tags.items():
                if isinstance(value, (list, tuple, set)):
                    if not value:
                        return []

                    matched = set().union(
                        *(self._index[dim][v] for v in value)
                    )
                else:
                    matched = self._index[dim].get(value, set())

                if candidate_ids is None:
                    candidate_ids = matched
                else:
                    candidate_ids &= matched

            if candidate_ids is None:
                candidate_ids = set(range(len(self._entries)))

        results = []
        for idx in candidate_ids:
            entry = self._entries[idx]
            if not self._matches_tags(entry["tags"], tags):
                continue

            row = {
                "value": entry["value"],
                **entry["tags"],
                "references": [
                    {
                        "id": ref_id,
                        "value": self._entries[ref_id]["value"],
                        "tags": dict(self._entries[ref_id]["tags"]),
                    }
                    for ref_id in entry["references"]
                ],
            }
            results.append(row)

        return results

    def query(self, **tags):
        return [row["value"] for row in self.query_with_tags(**tags)]

    def query_one(self, default=None, **tags):
        rows = self.query_with_tags(**tags)
        if len(rows) == 0:
            return default
        if len(rows) > 1:
            raise ValueError(f"Expected at most 1 result for {tags}, got {len(rows)}")
        return rows[0]["value"]