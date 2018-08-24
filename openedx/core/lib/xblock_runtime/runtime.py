from xblock.core import XBlock, XBlockAside
from xblock.field_data import ReadOnlyFieldData, SplitFieldData
from xblock.fields import Scope, ScopeIds
from xblock.runtime import Runtime, IdReader, IdGenerator

from openedx.core.lib.xblock_utils import xblock_local_resource_url
from .id_managers import OpaqueKeyReader, AsideKeyGenerator


class XBlockRuntime(Runtime):
    """
    This class manages a single instantiated XBlock, providing that XBlock with
    the standard XBlock runtime API (and some Open edX-specific additions)
    so that it can interact with the platform, and the platform can interact
    with it.
    """
    def __init__(self, system, scope_ids):
        # type: (XBlockRuntimeSystem, ScopeIds) -> None
        super(XBlockRuntime, self).__init__(
            id_reader=system.id_reader,
            mixins=(),
            services={
                "field-data": system.field_data,
            },
            default_class=None,
            select=None,
            id_generator=system.id_generator,
        )
        self._scope_ids = scope_ids

    def handler_url(self, block, handler_name, suffix='', query='', thirdparty=False):
        return system.handler_url(block, handler_name, suffix, query, thirdparty)

    def resource_url(self, resource):
        raise NotImplementedError("resource_url is not supported by Open edX.")

    def local_resource_url(self, block, uri):
        return xblock_local_resource_url(block, uri)

    def publish(self, block, event_type, event_data):
        if block.scope_ids != self._scope_ids:
            raise ValueError("XBlocks are not allowed to publish events for other XBlocks.")  # Is that true?
        pass  # TODO: publish events properly


class XBlockRuntimeSystem(object):
    """
    This class is essentially a factory for XBlockRuntimes. This is a
    long-lived object which provides the behavior specific to the application
    that wants to use XBlocks. Unlike XBlockRuntime, a single instance of this
    class can be used with many different XBlocks, whereas each XBlock gets its
    own instance of XBlockRuntime.
    """
    def __init__(
        self,
        handler_url,  # type: (Callable[[XBlock, string, string, string, bool], string]
        authored_data_kvs,  # type: InheritanceKeyValueStore
        student_data_kvs,  # type: InheritanceKeyValueStore
        authored_data_readonly=True  # type: bool
    ):
        """
        args:
            handler_url: A method that implements the XBlock runtime
                handler_url interface.
            authored_data_kvs: An InheritanceKeyValueStore used to retrieve
                any fields with UserScope.NONE
            student_data_kvs: An InheritanceKeyValueStore used to retrieve
                any fields with UserScope.ONE or UserScope.ALL
            authored_data_readonly: If true, this runtime system will not allow
                XBlocks to write to any UserScope.NONE fields.
        """
        self.handler_url = handler_url
        self.id_reader = OpaqueKeyReader()
        self.id_generator = AsideKeyGenerator()

        # Field data storage/retrieval:
        authored_data = inheriting_field_data(authored_data_kvs)
        student_data = student_data_kvs
        if authored_data_readonly:
            authored_data = ReadOnlyFieldData(authored_data)

        self.field_data = SplitFieldData({
            Scope.content: authored_data,
            Scope.settings: authored_data,
            Scope.parent: authored_data,
            Scope.children: authored_data,
            Scope.user_state_summary: student_data,
            Scope.user_state: student_data,
            Scope.user_info: student_data,
            Scope.preferences: student_data,
        })

    def get_block(self, learning_context, user_id, usage_id):
        # type: (string, UsageKey) -> XBlock

        def_id = self.id_reader.get_definition_id(usage_id)
        try:
            block_type = self.id_reader.get_block_type(def_id)
        except NoSuchDefinition:
            raise NoSuchUsage(repr(usage_id))

        scope_ids = ScopeIds(user_id, block_type, def_id, usage_id)
        runtime = XBlockRuntime(self, scope_ids)

        for_parent = None  # TODO

        block = runtime.construct_xblock(block_type, scope_ids, for_parent=for_parent)
        return block
