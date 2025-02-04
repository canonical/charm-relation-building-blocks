from typing import List, Optional, Union

import pytest
from ops import BoundEvent, CharmBase
from ops.testing import Context
from pydantic import BaseModel, Field

from charm_relation_building_blocks.data_models import DatabagModel
from charm_relation_building_blocks.relation_handlers import Receiver, Sender

RELATION_NAME = "app-data-relation"
# Note: if this is changed, the AppData concrete classes below need to change their constructors to match
APP_DATA_KEY = "key"
APP_DATA_VALUE = "value"


class AppData(DatabagModel, BaseModel):
    """Data model for the istio-info interface."""

    key: str = Field(
        description="Sample data key.",
        examples=["value"],
    )


class ReceiverRequirer(Receiver):
    """Class to handle the receiver side of a uni-direction application data relation as the requirer."""

    def __init__(
        self,
        charm: CharmBase,
        relation_name,
        refresh_event: Optional[Union[BoundEvent, List[BoundEvent]]] = None,
    ) -> None:
        """Initialize the IstioInfoRequirer object.

        Args:
            charm: The charm instance.
            relation_name: The name of the relation.
            refresh_event: An event or list of events that should trigger the library to process its relations.
                           By default, this charm already observes the relation_changed event.
        """
        super().__init__(charm, relation_name, AppData, refresh_event)


class SenderProvider(Sender):
    """Class to handle the sender side of a uni-direction application data relation as the provider."""

    def __init__(
        self,
        charm: CharmBase,
        key: str,
        relation_name,
        refresh_event: Optional[Union[BoundEvent, List[BoundEvent]]] = None,
    ) -> None:
        """Initialize the IstioInfoProvider object.

        Args:
            charm: The charm instance.
            key: data in the schema.
            relation_name: The name of the relation.
            refresh_event: An event or list of events that should trigger the library to publish data to its relations.
                           By default, this charm already observes the relation_joined and on_leader_elected events.
        """
        data = AppData(key=key)
        super().__init__(charm, data, relation_name, refresh_event)


class SenderProviderCharm(CharmBase):
    META = {
        "name": "provider",
        "provides": {RELATION_NAME: {"interface": RELATION_NAME}},
    }

    def __init__(self, framework):
        super().__init__(framework)
        self.relation_provider = SenderProvider(
            self, key=APP_DATA_VALUE, relation_name=RELATION_NAME
        )


@pytest.fixture()
def sender_provider_context():
    return Context(charm_type=SenderProviderCharm, meta=SenderProviderCharm.META)


class ReceiverRequirerCharm(CharmBase):
    META = {
        "name": "requirer",
        "requires": {RELATION_NAME: {"interface": "istio-info"}},
    }

    def __init__(self, framework):
        super().__init__(framework)
        self.relation_requirer = ReceiverRequirer(self, relation_name=RELATION_NAME)


@pytest.fixture()
def receiver_requirer_context():
    return Context(charm_type=ReceiverRequirerCharm, meta=ReceiverRequirerCharm.META)
