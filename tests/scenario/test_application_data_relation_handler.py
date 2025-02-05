from contextlib import nullcontext as does_not_raise
from typing import Union

import pytest
from ops.testing import Relation, State

from charm_relation_building_blocks.relation_handlers import DataChangedEvent

# Ignore F401 because fixtures are used, just not in the way ruff understands
from tests.scenario.utils import (  # noqa: F401
    APP_DATA_KEY,
    APP_DATA_VALUE,
    AppData,
    receiver_requirer_context,
    sender_provider_context,
)

RELATION_NAME = "app-data-relation"
INTERFACE_NAME = "app-data-interface"


def local_app_data_relation_state(leader: bool, local_app_data: dict = None) -> (Relation, State):
    """Return a testing State that has a single relation with the given local_app_data."""
    if local_app_data is None:
        local_app_data = {}

    relation = Relation(RELATION_NAME, INTERFACE_NAME, local_app_data=local_app_data)
    relations = [relation]

    state = State(
        relations=relations,
        leader=leader,
    )

    return relation, state


def test_provider_sender_sends_data_on_relation_joined(sender_provider_context):
    """Tests that a charm using ProviderSender sends the correct data to the relation on a relation joined event."""
    # Arrange
    relation, state = local_app_data_relation_state(leader=True)

    # Act
    sender_provider_context.run(sender_provider_context.on.relation_joined(relation), state=state)

    # Assert
    assert relation.local_app_data == {APP_DATA_KEY: APP_DATA_VALUE}


def test_provider_sends_data_on_leader_elected(sender_provider_context):
    """Tests that a charm using IstioInfoProvider sends the correct data to the relation on a leader elected event."""
    # Arrange
    relation, state = local_app_data_relation_state(leader=True)

    # Act
    sender_provider_context.run(sender_provider_context.on.leader_elected(), state=state)

    # Assert
    assert relation.local_app_data == {APP_DATA_KEY: APP_DATA_VALUE}


def test_provider_doesnt_send_data_when_not_leader(sender_provider_context):
    """Tests that a charm using the IstioInfoProvider does not send data if not the leader."""
    # Arrange
    relation, state = local_app_data_relation_state(leader=False)

    events = [
        sender_provider_context.on.relation_joined(relation),
        sender_provider_context.on.leader_elected(),
        sender_provider_context.on.config_changed(),  # just to have some other event
    ]
    for event in events:
        # Act
        sender_provider_context.run(event, state=state)

        # Assert
        assert relation.local_app_data == {}


@pytest.mark.parametrize(
    "local_app_data",
    [
        {},  # relation starts with empty data
        {APP_DATA_KEY: "not-the-real-data"},  # relation starts with stale data
    ],
)
def test_provider_is_ready(local_app_data, sender_provider_context):
    """Tests that a charm using the IstioInfoProvider correctly assesses whether the data sent is up to date."""
    # Arrange
    relation, state = local_app_data_relation_state(leader=True, local_app_data=local_app_data)

    with sender_provider_context(
        sender_provider_context.on.relation_joined(relation), state=state
    ) as manager:
        charm = manager.charm

        # Before executing the event that causes data to be emitted, the relation handler should not be ready
        assert not charm.relation_provider.is_ready()

        # After the data is sent, the provider should indicate ready
        manager.run()
        assert charm.relation_provider.is_ready()


def test_requirer_emits_info_changed_on_relation_data_changes(receiver_requirer_context):
    """Tests that a charm using IstioInfoRequirer emits a DataChangedEvent when the relation data changes."""
    # Arrange
    relation, state = local_app_data_relation_state(leader=False)

    # Act
    receiver_requirer_context.run(
        receiver_requirer_context.on.relation_changed(relation), state=state
    )

    # Assert we emitted the info changed event
    # Note: emitted_events also includes the event we executed above in .run()
    assert len(receiver_requirer_context.emitted_events) == 2
    assert isinstance(receiver_requirer_context.emitted_events[1], DataChangedEvent)


@pytest.mark.parametrize(
    "relations, expected_data, context_raised",
    [
        ([], None, does_not_raise()),  # no relations
        (
            [Relation(RELATION_NAME, INTERFACE_NAME, remote_app_data={})],
            None,
            does_not_raise(),
        ),  # one empty relation
        (
            [
                Relation(
                    RELATION_NAME,
                    INTERFACE_NAME,
                    remote_app_data={APP_DATA_KEY: APP_DATA_VALUE},
                )
            ],
            AppData(key=APP_DATA_VALUE),
            does_not_raise(),
        ),  # one populated relation
        (
            [
                Relation(
                    RELATION_NAME,
                    INTERFACE_NAME,
                    remote_app_data={APP_DATA_KEY: APP_DATA_VALUE},
                ),
                Relation(
                    RELATION_NAME,
                    INTERFACE_NAME,
                    remote_app_data={APP_DATA_KEY: APP_DATA_VALUE},
                ),
            ],
            None,
            pytest.raises(ValueError),
        ),  # stale data
    ],
)
def test_requirer_get_data(relations, expected_data, context_raised, receiver_requirer_context):
    """Tests that IstioInfoRequirer.get_data() returns correctly."""
    state = State(
        relations=relations,
        leader=False,
    )

    with receiver_requirer_context(
        receiver_requirer_context.on.update_status(), state=state
    ) as manager:
        charm = manager.charm

        with context_raised:
            data = charm.relation_requirer.get_data()
            assert compare_app_data(data, expected_data)


@pytest.mark.parametrize(
    "relations, expected_data, context_raised",
    [
        ([], [], does_not_raise()),  # no relations
        (
            [Relation(RELATION_NAME, INTERFACE_NAME, remote_app_data={})],
            [None],
            does_not_raise(),
        ),  # one empty relation
        (
            [
                Relation(
                    RELATION_NAME,
                    INTERFACE_NAME,
                    remote_app_data={APP_DATA_KEY: APP_DATA_VALUE},
                )
            ],
            [AppData(key=APP_DATA_VALUE)],
            does_not_raise(),
        ),  # one populated relation
        (
            [
                Relation(
                    RELATION_NAME,
                    INTERFACE_NAME,
                    remote_app_data={APP_DATA_KEY: APP_DATA_VALUE + "1"},
                ),
                Relation(RELATION_NAME, INTERFACE_NAME, remote_app_data={}),
                Relation(
                    RELATION_NAME,
                    INTERFACE_NAME,
                    remote_app_data={APP_DATA_KEY: APP_DATA_VALUE + "3"},
                ),
            ],
            [
                AppData(key=APP_DATA_VALUE + "1"),
                None,
                AppData(key=APP_DATA_VALUE + "3"),
            ],
            does_not_raise(),
        ),  # many related applications, some with missing data
    ],
)
def test_requirer_get_data_from_all_relations(
    relations, expected_data, context_raised, receiver_requirer_context
):
    """Tests that IstioInfoRequirer.get_data_from_all_relations() returns correctly."""
    state = State(
        relations=relations,
        leader=False,
    )

    with receiver_requirer_context(
        receiver_requirer_context.on.update_status(), state=state
    ) as manager:
        charm = manager.charm

        with context_raised:
            data = sort_app_data(charm.relation_requirer.get_data_from_all_relations())
            expected_data = sort_app_data(expected_data)
            for actual, expected in zip(data, expected_data):
                assert compare_app_data(actual, expected)


def sort_app_data(data):
    """Return sorted version of the list of relation data objects."""
    return sorted(data, key=lambda x: x.key if x else "")


def compare_app_data(data1: Union[AppData, None], data2: Union[AppData, None]):
    """Compare two AppData objects, tolerating when one or both is None."""
    if data1 is None and data2 is None:
        return True
    if data1 is None or data2 is None:
        return False
    return data1.model_dump() == data2.model_dump()
