# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Relation handler base classes for relations using application data."""

from typing import List, Optional, Type, Union

from ops import BoundEvent, CharmBase, CharmEvents, EventBase, EventSource, Object

from charm_relation_building_blocks.data_models import DatabagModel, DataValidationError


class DataChangedEvent(EventBase):
    """Charm Event triggered when the relation data has changed."""


class ReceiverCharmEvents(CharmEvents):
    """Events raised by the data receiver side of the interface."""

    data_changed = EventSource(DataChangedEvent)


class Receiver(Object):
    """Base class for the receiver side of a generic uni-directional application data relation."""

    on = ReceiverCharmEvents()  # type: ignore[reportAssignmentType]

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str,
        data_model: Type[DatabagModel],
        refresh_event: Optional[Union[BoundEvent, List[BoundEvent]]] = None,
    ) -> None:
        """Initialize the Receiver object.

        Args:
            charm: The charm instance that the relation is attached to.
            relation_name: The name of the relation.
            data_model: The pydantic data model class to use for instantiating data instances.
            refresh_event: An event or list of events that should trigger this library to process its relations.
                           By default, this charm already observes the relation_changed event.
        """
        super().__init__(charm, relation_name)

        self._charm = charm
        self._relation_name = relation_name
        self._schema = data_model

        if not refresh_event:
            refresh_event = []
        if isinstance(refresh_event, BoundEvent):
            refresh_event = [refresh_event]
        for ev in refresh_event:
            self.framework.observe(ev, self.on_relation_changed)

        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed, self.on_relation_changed
        )

    def __len__(self):
        """Return the number of related applications."""
        return len(self.get_relations())

    def on_relation_changed(self, _: EventBase) -> None:
        """Handle when the remote application data changed."""
        self.on.data_changed.emit()

    def get_relations(self):
        """Return the relation instances for applications related to us on the monitored relation."""
        return self._charm.model.relations.get(self._relation_name, ())

    def get_data(self) -> Optional[DatabagModel]:
        """Return data for at most one related application, raising if more than one is available.

        Useful for charms that always expect exactly one related application.  It is recommended that those charms also
        set limit=1 for that relation in charmcraft.yaml.  Returns None if no data is available (either because no
        applications are related to us, or because the related application has not sent data).
        """
        relations = self.get_relations()
        if len(relations) == 0:
            return None
        if len(relations) > 1:
            # TODO: Different exception type?
            raise ValueError("Cannot get_info when more than one application is related.")

        raw_data = relations[0].data.get(relations[0].app)
        if not raw_data:
            return None

        # Static analysis errors saying the keys may not be strings.  Protect against this by converting them.
        raw_data = {str(k): v for k, v in raw_data.items()}

        return self._schema(**raw_data)

    def get_data_from_all_relations(self) -> List[DatabagModel]:
        """Return a list of data objects from all relations."""
        relations = self.get_relations()
        info_list = []
        for i, relation in enumerate(relations):
            data_dict = relation.data.get(relation.app)
            if not data_dict:
                info_list.append(None)
                continue

            # Static analysis errors saying the keys may not be strings.  Protect against this by converting them.
            data_dict = {str(k): v for k, v in data_dict.items()}
            info_list.append(self._schema(**data_dict))
        return info_list


class Sender(Object):
    """Base class for the sending side of a generic uni-directional application data relation."""

    def __init__(
        self,
        charm: CharmBase,
        data: DatabagModel,
        relation_name: str,
        refresh_event: Optional[Union[BoundEvent, List[BoundEvent]]] = None,
    ) -> None:
        """Initialize the IstioInfoProvider object.

        Args:
            charm: The charm instance.
            data: An instance of the data sent on this relation.
            relation_name: The name of the relation.
            refresh_event: An event or list of events that should trigger the library to publish data to its relations.
                           By default, this charm already observes the relation_joined and on_leader_elected events.
        """
        super().__init__(charm, relation_name)

        self._charm = charm
        self._data = data
        self._relation_name = relation_name

        if not refresh_event:
            refresh_event = []
        if isinstance(refresh_event, BoundEvent):
            refresh_event = [refresh_event]
        for ev in refresh_event:
            self.framework.observe(ev, self.handle_send_data_event)

        self.framework.observe(
            self._charm.on[self._relation_name].relation_joined, self.handle_send_data_event
        )
        # Observe leader elected events because only the leader should send data, and we don't want to miss a case where
        # the relation_joined event happens during a leadership change.
        self.framework.observe(self._charm.on.leader_elected, self.handle_send_data_event)

    def handle_send_data_event(self, _: EventBase) -> None:
        """Handle events that should send data to the relation."""
        if self._charm.unit.is_leader():
            self.send_data()

    def _get_relations(self):
        """Return the applications related to us under the monitored relation."""
        return self._charm.model.relations.get(self._relation_name, ())

    def send_data(self):
        """Post istio-info to all related applications.

        If the calling charm needs to handle cases where the data cannot be sent, it should observe the
        send_info_failed event.  This, however, is better handled by including a check on the is_ready method
        in the charm's collect_status event.
        """
        info_relations = self._get_relations()
        for relation in info_relations:
            self._data.dump(relation.data[self._charm.app])

    def _is_relation_data_up_to_date(self):
        """Confirm that the Istio info data we should publish is published to all related applications."""
        expected_app_data = self._data
        for relation in self._get_relations():
            try:
                app_data = self._data.__class__.load(relation.data[self._charm.app])
            except DataValidationError:
                return False
            if app_data != expected_app_data:
                return False
        return True

    def is_ready(self):
        """Return whether the data has been published to all related applications.

        Useful for charms that handle the collect_status event.
        """
        return self._is_relation_data_up_to_date()
