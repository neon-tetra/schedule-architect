from collections import defaultdict


class VarRegistry:
    """
    A tag-based registry for storing and querying CP-SAT variables
    (or any objects) by arbitrary keyword dimensions.

    Usage:
        registry = VarRegistry()
        registry.add(var, agent=3, day=2, slot=5, skill="phones")
        registry.query(agent=3, skill="phones")  # -> list of vars
    """

    def __init__(self):
        self._entries = []                          # list of (obj, tags_dict)
        self._index = defaultdict(lambda: defaultdict(set))  # dim -> value -> set of entry indices

    def add(self, obj, **tags):
        idx = len(self._entries)
        self._entries.append((obj, tags))
        for dim, value in tags.items():
            self._index[dim][value].add(idx)

    def query(self, **tags):
        if not tags:
            return [obj for obj, _ in self._entries]

        # intersect the index sets for each tag
        sets = [
            self._index[dim][value]
            for dim, value in tags.items()
        ]
        matching = set.intersection(*sets)
        return [self._entries[i][0] for i in matching]

    def query_one(self, **tags):
        results = self.query(**tags)
        if len(results) != 1:
            raise ValueError(
                f"Expected exactly 1 result for {tags}, got {len(results)}"
            )
        return results[0]

    def __len__(self):
        return len(self._entries)

    def __repr__(self):
        return f"VarRegistry({len(self._entries)} entries)"