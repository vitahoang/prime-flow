from folio import groups, users


def test_direct_members_and_listing(world):
    s = world["store"]
    g = s.add_group(world["ws"], "Studio", [world["marcus"], world["olive"]])
    assert groups.direct_members(s, g) == [world["marcus"], world["olive"]]
    assert groups.groups_listing(s, world["marcus"]) == [g]


def test_group_tree_stops_at_max_depth(world):
    s = world["store"]
    ids = [s.add_group(world["ws"], f"Level {i}", [world["olive"]]) for i in range(5)]
    for parent, child in zip(ids, ids[1:]):
        s.add_subgroup(parent, child)
    lines = list(groups.group_tree(s, ids[0], max_depth=2))
    assert lines[0].startswith("Level 0")
    assert lines[-1].strip() == "..."


def test_guest_is_external(world):
    s = world["store"]
    assert users.is_external(s, world["lena"])
    assert not users.is_external(s, world["olive"])
    assert users.display(s, world["lena"]).endswith("(guest)")


def test_find_by_email(world):
    s = world["store"]
    assert users.find_by_email(s, world["ws"], " Marcus@HollisGrey.com").id == world["marcus"]
