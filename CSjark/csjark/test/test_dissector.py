"""
Module for testing the dissector module.

Tests the output of generating dissectors.
"""
import sys, os
from attest import Tests, assert_hook, contexts

import dissector
from config import StructConfig, Trailer


def compare_lua(code, template, write_to_file=''):
    """Test that generated lua code equals what is expected."""
    if write_to_file:
        with open(write_to_file, 'a') as f:
            f.write('%s\n' % code.replace('\t',''))
    def simplify(text):
        return ''.join(text.strip().split())
    return simplify(code) == simplify(template)


# Test EnumField
enums = Tests()

@enums.context
def create_enum_field():
    """Create a Protocol instance with some fields."""
    proto = dissector.Protocol('test', None, None)
    proto.add_enum('enum', 'int32', 4, dict(enumerate('ABCDE')))
    yield proto.fields[0]
    del proto

@enums.test
def enum_def(field):
    """Test that EnumField generates valid defintion code."""
    assert field
    assert compare_lua(field.get_definition(), '''
    f.enum = ProtoField.int32("test.enum", "enum",
        nil, {[0]="A", [1]="B", [2]="C", [3]="D", [4]="E"})
    ''')

@enums.test
def enum_code(field):
    """Test that EnumField generates correct code."""
    assert isinstance(field, dissector.EnumField)
    assert compare_lua(field.get_code(0), '''
    local enum = subtree:add(f.enum, buffer(0, 4))
    local test = {[0]="A", [1]="B", [2]="C", [3]="D", [4]="E"}
    if (test[buffer(0, 4):int()] == nil) then
        enum:add_expert_info(PI_MALFORMED, PI_WARN,
            "Invalid value, not in (0, 1, 2, 3, 4)")
    end
    ''')


# Test ArrayField
arrays = Tests()

@arrays.context
def create_array_field():
    """Create a Protocol instance with some fields."""
    proto = dissector.Protocol('test', None, None)
    proto.add_array('arr', 'float', 4, [1, 2, 3])
    proto.add_array('str', 'string', 30, [2])
    yield proto.fields[0], proto.fields[1]
    del proto

@arrays.test
def arrays_def(one, two):
    """Test that ArrayField generates valid defintion code."""
    assert one and two
    assert compare_lua(one.get_definition(), '''
    -- Array definition for arr
    f.arr_0 = ProtoField.bytes("test.arr", "arr")
    f.arr_1 = ProtoField.bytes("test.arr", "arr")
    f.arr_2 = ProtoField.bytes("test.arr", "arr")
    f.arr__0 = ProtoField.float("test.arr.0", "[0]")
    f.arr__1 = ProtoField.float("test.arr.1", "[1]")
    f.arr__2 = ProtoField.float("test.arr.2", "[2]")
    f.arr__3 = ProtoField.float("test.arr.3", "[3]")
    f.arr__4 = ProtoField.float("test.arr.4", "[4]")
    f.arr__5 = ProtoField.float("test.arr.5", "[5]")
    ''')
    assert compare_lua(two.get_definition(), '''
    -- Array definition for str
    f.str_0 = ProtoField.string("test.str", "str")
    f.str_1 = ProtoField.string("test.str", "str")
    f.str__0 = ProtoField.string("test.str.0", "[0]")
    f.str__1 = ProtoField.string("test.str.1", "[1]")
    ''')

@arrays.test
def arrays_code(one, two):
    """Test that ArrayField generates correct code."""
    assert isinstance(one, dissector.ArrayField)
    assert compare_lua(one.get_code(0), '''
    -- Array handling for arr
    local arraytree = subtree:add(f.arr_0, buffer(0, 24))
    arraytree:set_text("arr (array: 6 x float)")
    local subarraytree = arraytree:add(f.arr_1, buffer(0, 24))
    subarraytree:set_text("(array: 6 x float)")
    local subsubarraytree = subarraytree:add(f.arr_2, buffer(0, 12))
    subsubarraytree:set_text("(array: 3 x float)")
    subsubarraytree:add(f.arr__0, buffer(0, 4))
    subsubarraytree:add(f.arr__1, buffer(4, 4))
    subsubarraytree:add(f.arr__2, buffer(8, 4))
    local subsubarraytree = subarraytree:add(f.arr_3, buffer(12, 12))
    subsubarraytree:set_text("(array: 3 x float)")
    subsubarraytree:add(f.arr__3, buffer(12, 4))
    subsubarraytree:add(f.arr__4, buffer(16, 4))
    subsubarraytree:add(f.arr__5, buffer(20, 4))
    ''')

@arrays.test
def arrays_str(one, two):
    """Test that ArrayField generates code for char array."""
    assert isinstance(two, dissector.ArrayField)
    assert compare_lua(two.get_code(0), '''
    -- Array handling for str
    local arraytree = subtree:add(f.str_0, buffer(0, 60))
    arraytree:set_text("str (array: 2 x string)")
    arraytree:add(f.str__0, buffer(0, 30))
    arraytree:add(f.str__1, buffer(30, 30))
    ''')


# Test ProtocolField
protofields = Tests()

@protofields.context
def create_protocol_field():
    """Create a Protocol instance with some fields."""
    proto = dissector.Protocol('test', None, None)
    proto.add_protocol('test', 8, 32, 'proto_one')
    proto.add_protocol('test2', 9, 64, 'proto_two')
    yield proto.fields[0], proto.fields[1]
    del proto

@protofields.test
def proto_field_def(one, two):
    """Test that ProtocolField generates no defintion code."""
    assert one and two
    assert one.get_definition() is None
    assert two.get_definition() is None

@protofields.test
def proto_field_code(one, two):
    """Test that ProtocolField generates correct code."""
    assert isinstance(one, dissector.ProtocolField)
    assert isinstance(two, dissector.ProtocolField)
    assert compare_lua(one.get_code(0), '''
    local subsubtree = subtree:add("test:")
    luastructs_dt:try(8, buffer(0, 32):tvb(), pinfo, subsubtree)
    ''')
    assert compare_lua(two.get_code(32), '''
    local subsubtree = subtree:add("test2:")
    luastructs_dt:try(9, buffer(32, 64):tvb(), pinfo, subsubtree)
    ''')


# Test BitField
bits = Tests()

@bits.context
def create_bit_field():
    """Create a Protocol instance with some fields."""
    proto = dissector.Protocol('test', None, None)
    bits = [(1, 1, 'R', {0: 'No', 1: 'Yes'}),
            (2, 1, 'B', {0: 'No', 1: 'Yes'}),
            (3, 1, 'G', {0: 'No', 1: 'Yes'})]
    proto.add_bit('bit1', 'int32', 4, bits)
    proto.add_bit('bit2', 'uint16', 2, bits)
    yield proto.fields[0], proto.fields[1]
    del proto

@bits.test
def bitfield_def(one, two):
    """Test that BitField generates valid defintion code."""
    assert one and two
    assert compare_lua(one.get_definition(), '''
    -- Bitstring definitions for bit1
    f.bit1 = ProtoField.uint32("test.bit1", "bit1 (bitstring)", base.HEX)
    f.bit1_R = ProtoField.uint32("test.bit1.R",
            "R", nil, {[0]="No", [1]="Yes"}, 0x1)
    f.bit1_B = ProtoField.uint32("test.bit1.B",
            "B", nil, {[0]="No", [1]="Yes"}, 0x2)
    f.bit1_G = ProtoField.uint32("test.bit1.G",
            "G", nil, {[0]="No", [1]="Yes"}, 0x4)
    ''')
    assert compare_lua(two.get_definition(), '''
    -- Bitstring definitions for bit2
    f.bit2 = ProtoField.uint16("test.bit2", "bit2 (bitstring)", base.HEX)
    f.bit2_R = ProtoField.uint16("test.bit2.R",
            "R", nil, {[0]="No", [1]="Yes"}, 0x1)
    f.bit2_B = ProtoField.uint16("test.bit2.B",
            "B", nil, {[0]="No", [1]="Yes"}, 0x2)
    f.bit2_G = ProtoField.uint16("test.bit2.G",
            "G", nil, {[0]="No", [1]="Yes"}, 0x4)
    ''')

@bits.test
def bitfield_code(one, two):
    """Test that BitField generates valid code."""
    assert compare_lua(one.get_code(0), '''
    -- Bitstring handling for bit1
    local bittree = subtree:add(f.bit1, buffer(0, 4))
    bittree:add(f.bit1_R, buffer(0, 4))
    bittree:add(f.bit1_B, buffer(0, 4))
    bittree:add(f.bit1_G, buffer(0, 4))
    ''')
    assert compare_lua(two.get_code(4), '''
    -- Bitstring handling for bit2
    local bittree = subtree:add(f.bit2, buffer(4, 2))
    bittree:add(f.bit2_R, buffer(4, 2))
    bittree:add(f.bit2_B, buffer(4, 2))
    bittree:add(f.bit2_G, buffer(4, 2))
    ''')


# Test RangeField
ranges = Tests()

@ranges.context
def create_range_field():
    """Create a Protocol instance with some fields."""
    proto = dissector.Protocol('test', None, None)
    proto.add_range('range', 'float', 4, 0, 10)
    yield proto.fields[0]
    del proto

@ranges.test
def ranges_def(field):
    """Test that RangeField generates valid defintion code."""
    assert field
    assert compare_lua(field.get_definition(), '''
    f.range = ProtoField.float("test.range", "range")
    ''')

@ranges.test
def ranges_code(field):
    """Test that RangeField generates valid code."""
    assert compare_lua(field.get_code(0), '''
    local range = subtree:add(f.range, buffer(0, 4))
    if (buffer(0, 4):float() < 0) then
    range:add_expert_info(PI_MALFORMED, PI_WARN, "Should be larger than 0")
    end
    if (buffer(0, 4):float() > 10) then
    range:add_expert_info(PI_MALFORMED, PI_WARN, "Should be smaller than 10")
    end
    ''')


# Test TrailerField
trailer = Tests()

@trailer.context
def create_trailer_field():
    """Create a Protocol instance with some fields."""
    proto = dissector.Protocol('test', None, None)
    conf = StructConfig('tester')
    rules = [Trailer(conf, {'name': 'ber', 'count': 3, 'size': 8}),
             Trailer(conf, {'name': 'ber', 'count': 'count'})]
    proto.add_trailer('count', 'int32', 4, rules)
    yield conf, proto.fields[0]
    del conf, proto

@trailer.test
def trailer_code(conf, field):
    """Test that TrailerField generates correct code."""
    assert len(conf.trailers) == 2
    assert isinstance(field, dissector.TrailerField)
    assert conf.trailers[0].member is None
    assert conf.trailers[1]._field is field
    assert compare_lua(field.get_code(0), '''
    subtree:add(f.count, buffer(0, 4))
    ''')
    assert compare_lua(field.get_definition(), '''
    f.count = ProtoField.int32("test.count", "count")
    ''')


# Test Field
fields = Tests()

@fields.context
def create_field():
    """Create a Protocol instance with some fields."""
    proto = dissector.Protocol('test', None, None)
    proto.add_field('one', 'float', 4)
    proto.add_field('two', 'string', 12)
    yield proto.fields[0], proto.fields[1]
    del proto

@fields.test
def fields_def(one, two):
    """Test that Field generates valid defintion code."""
    assert one and two
    assert compare_lua(one.get_definition(), '''
    f.one = ProtoField.float("test.one", "one")
    ''')
    assert compare_lua(two.get_definition(), '''
    f.two = ProtoField.string("test.two", "two")
    ''')

@fields.test
def fields_code(one, two):
    """Test that Field generates valid code."""
    assert compare_lua(one.get_code(0), 'subtree:add(f.one, buffer(0, 4))')
    assert compare_lua(two.get_code(0), 'subtree:add(f.two, buffer(0, 12))')


# Test Protocol
protos = Tests()

@protos.context
def create_protos():
    """Create a Protocol instance with some fields."""
    conf = StructConfig('tester')
    conf.id = 25
    conf.description = 'This is a test'

    rules = [Trailer(conf, {'name': 'missing', 'count': 'missing', 'size': 0}),
             Trailer(conf, {'name': 'simple', 'count': 1, 'size': 4}),
             Trailer(conf, {'name': 'bur', 'count': 3, 'size': 8}),
             Trailer(conf, {'name': 'ber', 'count': 'count'})]
    proto = dissector.Protocol('tester', None, conf)

    proto.add_field('one', 'float', 4)
    proto.add_range('range', 'float', 4, 0, 10)
    proto.add_array('array', 'float', 4, [1, 2, 3])
    proto.add_array('str', 'string', 30, [2])
    proto.add_trailer('count', 'int32', 4, rules)
    yield proto
    del StructConfig.configs['tester'], proto

@protos.test
def protos_id(proto):
    """Test that Protocol has id, description and var members."""
    assert proto
    assert proto.id == 25
    assert proto.description == 'This is a test'
    assert proto.var == 'proto_tester'
    assert isinstance(proto.fields[0], dissector.Field)

@protos.test
def protos_trailer(proto):
    """Test that the Protocol has trailers."""
    assert proto.conf
    assert proto.conf.trailers
    assert len(proto.conf.trailers) == 4
    assert proto.conf.trailers[2].name == 'bur'
    assert proto.conf.trailers[3].count is None
    assert proto.conf.trailers[3]._field is not None
    assert proto.conf.trailers[0]._field is None

@protos.test
def protos_create_dissector(proto):
    """Test that Protocol generates valid dissector code."""
    assert proto
    assert compare_lua(proto.create(), '''
    -- Dissector for struct: tester: This is a test
    local proto_tester = Proto("tester", "This is a test")
    local luastructs_dt = DissectorTable.get("luastructs.message")
    -- ProtoField defintions for struct: tester
    local f = proto_tester.fields
    f.one = ProtoField.float("tester.one", "one")
    f.range = ProtoField.float("tester.range", "range")
    -- Array definition for array
    f.array_0 = ProtoField.bytes("tester.array", "array")
    f.array_1 = ProtoField.bytes("tester.array", "array")
    f.array_2 = ProtoField.bytes("tester.array", "array")
    f.array__0 = ProtoField.float("tester.array.0", "[0]")
    f.array__1 = ProtoField.float("tester.array.1", "[1]")
    f.array__2 = ProtoField.float("tester.array.2", "[2]")
    f.array__3 = ProtoField.float("tester.array.3", "[3]")
    f.array__4 = ProtoField.float("tester.array.4", "[4]")
    f.array__5 = ProtoField.float("tester.array.5", "[5]")
    -- Array definition for str
    f.str_0 = ProtoField.string("tester.str", "str")
    f.str_1 = ProtoField.string("tester.str", "str")
    f.str__0 = ProtoField.string("tester.str.0", "[0]")
    f.str__1 = ProtoField.string("tester.str.1", "[1]")
    f.count = ProtoField.int32("tester.count", "count")
    -- Dissector function for struct: tester
    function proto_tester.dissector(buffer, pinfo, tree)
    local subtree = tree:add(proto_tester, buffer())
    pinfo.cols.info:append(" (" .. proto_tester.description .. ")")
    subtree:add(f.one, buffer(0, 4))
    local range = subtree:add(f.range, buffer(4, 4))
    if (buffer(4, 4):float() < 0) then
    range:add_expert_info(PI_MALFORMED, PI_WARN, "Should be larger than 0")
    end
    if (buffer(4, 4):float() > 10) then
    range:add_expert_info(PI_MALFORMED, PI_WARN, "Should be smaller than 10")
    end
    -- Array handling for array
    local arraytree = subtree:add(f.array_0, buffer(8, 24))
    arraytree:set_text("array (array: 6 x float)")
    local subarraytree = arraytree:add(f.array_1, buffer(8, 24))
    subarraytree:set_text("(array: 6 x float)")
    local subsubarraytree = subarraytree:add(f.array_2, buffer(8, 12))
    subsubarraytree:set_text("(array: 3 x float)")
    subsubarraytree:add(f.array__0, buffer(8, 4))
    subsubarraytree:add(f.array__1, buffer(12, 4))
    subsubarraytree:add(f.array__2, buffer(16, 4))
    local subsubarraytree = subarraytree:add(f.array_3, buffer(20, 12))
    subsubarraytree:set_text("(array: 3 x float)")
    subsubarraytree:add(f.array__3, buffer(20, 4))
    subsubarraytree:add(f.array__4, buffer(24, 4))
    subsubarraytree:add(f.array__5, buffer(28, 4))
    -- Array handling for str
    local arraytree = subtree:add(f.str_0, buffer(32, 60))
    arraytree:set_text("str (array: 2 x string)")
    arraytree:add(f.str__0, buffer(32, 30))
    arraytree:add(f.str__1, buffer(62, 30))
    subtree:add(f.count, buffer(92, 4))
    -- Trailers handling for struct: tester
    local trailer = Dissector.get("simple")
    trailer:call(buffer(96):tvb(), pinfo, tree)
    for i = 0, 3 do
    local trailer = Dissector.get("bur")
    trailer:call(buffer(100+(i*8),8):tvb(), pinfo, tree)
    end
    local trailer = Dissector.get("ber")
    trailer:call(buffer(124):tvb(), pinfo, tree)
    end
    luastructs_dt:add(25, proto_tester)
    ''')
