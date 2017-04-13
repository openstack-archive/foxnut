"""
SQLAlchemy models for baremetal compute service.
"""

try:
    import simplejson as json
except ImportError:
    import json
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import Table, Column
from sqlalchemy import Integer, String, DateTime, Boolean, Enum, Text
from sqlalchemy import ForeignKey, TypeDecorator
from sqlalchemy.ext import mutable
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func


SERVER_STATUS = Enum('null', 'shelving', 'shelved', 'building', 'builded', 'checking', 'checked',
                     'deploying', 'deployed', 'testing', 'product')

Base = declarative_base()


user_role_table = Table('user_role_relation', Base.metadata,
                        Column('user_uuid', String(36), ForeignKey('users.uuid')),
                        Column('role_uuid', String(36), ForeignKey('roles.uuid')))

role_server_table = Table('role_server_relation', Base.metadata,
                          Column('role_uuid', String(36), ForeignKey('roles.uuid')),
                          Column('server_uuid', String(36), ForeignKey('servers.uuid')))

role_command_table = Table('role_command_relation', Base.metadata,
                           Column('role_uuid', String(36), ForeignKey('roles.uuid')),
                           Column('command_uuid', String(36), ForeignKey('command_aliases.uuid')))


class JsonEncodedDict(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        return json.loads(value)


mutable.MutableDict.associate_with(JsonEncodedDict)


class VenusBase():
    uuid = Column(String(36), primary_key=True)
    name = Column(String(16))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(32))
    deleted = Column(Boolean, default=0)
    comment = Column(Text, default='')


class ProductBase(VenusBase):
    vendor = Column(String(16))
    model = Column(String(32))
    status = Column(Enum('active', 'error'), default='active')


class DataCenter(Base, VenusBase):
    __tablename__ = 'datacenters'
    location = Column(String(64))
    racks = relationship('Rack', back_populates='datacenter')

    @hybrid_property
    def sub_resources(self):
        return {'racks': self.racks}


class Rack(Base, VenusBase):
    __tablename__ = 'racks'
    dc_uuid = Column(String(36), ForeignKey('datacenters.uuid'), nullable=False)
    height = Column(Integer)
    electricity = Column(Integer)
    rack_limit = Column(Integer)
    datacenter = relationship('DataCenter', back_populates='racks')
    servers = relationship('Server', back_populates='rack')
    switches = relationship('Switch', back_populates='rack')

    @hybrid_property
    def sub_resources(self):
        return {'servers': self.servers, 'switches': self.switches}


class Server(Base, ProductBase):
    """Represents a bare metal server"""
    __tablename__ = 'servers'
    domain = Column(String(64))
    power_status = Column(Boolean, default=True)
    sn = Column(String(32), unique=True)
    cpu_model = Column(String(32))
    cpu_count = Column(Integer)
    mem_total = Column(Integer)
    raid_model = Column(String(32))
    system = Column(String(16))
    rack_layer = Column(String(8))
    role = Column(String(10))
    ipmi_ip = Column(String(64))
    ipmi_netmask = Column(String(64))
    ipmi_gateway = Column(String(64))
    mgm_ip = Column(String(64))
    mgm_mac = Column(String(64))
    mgm_netmask = Column(String(64))
    mgm_gateway = Column(String(64))
    raid_conf = Column(JsonEncodedDict(1000))
    launched_at = Column(DateTime(32))
    rack_uuid = Column(String(36), ForeignKey('racks.uuid'))
    dc_uuid = Column(String(36), ForeignKey('datacenters.uuid'))
    build_state = Column(Enum('building', 'unbuild', 'absent'))
    state = Column(SERVER_STATUS)
    rack = relationship('Rack', back_populates='servers')
    roles = relationship('Role', secondary=role_server_table, back_populates='servers')
    disks = relationship('Disk', back_populates='server')
    ports = relationship('ServerPort', back_populates='server')

    @hybrid_property
    def sub_resources(self):
        return {'ports': self.ports, 'disks': self.disks}


class Switch(Base, ProductBase):
    """Represents a switch."""
    __tablename__ = 'switches'
    name = Column(String(64), unique=True)
    power_status = Column(Boolean, default=True)
    sn = Column(String(32), unique=True)
    rack_layer = Column(String(8))
    role = Column(String(10))
    mgm_ip = Column(String(64))
    mgm_mac = Column(String(64))
    launched_at = Column(DateTime(32))
    rack_uuid = Column(String(36), ForeignKey('racks.uuid'))
    dc_uuid = Column(String(36), ForeignKey('datacenters.uuid'))
    rack = relationship('Rack', back_populates='switches')
    ports = relationship('SwitchPort', back_populates='switch')

    @hybrid_property
    def sub_resources(self):
        return {'ports': self.ports}


class Disk(Base, ProductBase):
    """Represents a disk."""
    __tablename__ = 'disks'
    server_uuid = Column(String(36), ForeignKey('servers.uuid'))
    wwn = Column(String(64), unique=True)
    disk_type = Column(Enum('SSD', 'HDD'))
    total_gb = Column(Integer)
    support_discard = Column(String(8))
    server = relationship('Server', back_populates='disks')


class ServerPort(Base, ProductBase):
    """Represents a network port."""
    __tablename__ = 'server_ports'
    server_uuid = Column(String(36), ForeignKey('servers.uuid'), nullable=False)
    switch_port_uuid = Column(String(36), ForeignKey('switch_ports.uuid'))
    mac_addr = Column(String(64), unique=True)
    ip_addr = Column(String(64))
    netmask = Column(String(64))
    vlan = Column(String(64))
    vlan_type = Column(String(64))
    speed = Column(Integer)
    switch_port = relationship('SwitchPort', uselist=False, back_populates='server_port')
    server = relationship('Server', back_populates='ports', lazy='subquery')

    @hybrid_property
    def sub_resources(self):
        self.server
        return {'switch_port': self.switch_port}


class SwitchPort(Base, ProductBase):
    """Represents a network port."""
    __tablename__ = 'switch_ports'
    switch_uuid = Column(String(36), ForeignKey('switches.uuid'), nullable=False)
    mac_addr = Column(String(64), unique=True)
    ip_addr = Column(String(64))
    netmask = Column(String(64))
    vlan = Column(String(64))
    vlan_type = Column(String(64))
    speed = Column(Integer)
    server_port = relationship('ServerPort', uselist=False, back_populates='switch_port')
    switch = relationship('Switch', back_populates='ports', lazy='subquery')

    @hybrid_property
    def sub_resources(self):
        self.switch
        return {'server_port': self.server_port}


class User(Base, VenusBase):
    __tablename__ = 'users'
    name = Column(String(32), unique=True, nullable=False)
    user_type = Column(Enum('ldap', 'normal'), default='normal')
    password = Column(String(100))
    is_active = Column(Boolean, default=True)
    roles = relationship('Role', secondary=user_role_table, back_populates='users')

    @hybrid_property
    def sub_resources(self):
        self.roles
        return {'roles': self.roles}


class Role(Base, VenusBase):
    __tablename__ = 'roles'
    name = Column(String(32), unique=True, nullable=False)
    commands = Column(Text)
    users = relationship('User', secondary=user_role_table, back_populates='roles')
    servers = relationship('Server', secondary=role_server_table, back_populates='roles')
    command_aliases = relationship('CommandAlias', secondary=role_command_table, back_populates='roles')

    @hybrid_property
    def sub_resources(self):
        self.command_aliases
        return {'command_aliases': self.command_aliases}

    @validates('name')
    def convert_upper(self, key, value):
        return value.upper()


class CommandAlias(Base, VenusBase):
    __tablename__ = 'command_aliases'
    name = Column(String(32), unique=True, nullable=False)
    commands = Column(Text, nullable=False)
    roles = relationship('Role', secondary=role_command_table, back_populates='command_aliases')

    @validates('name')
    def convert_upper(self, key, value):
        return value.upper()


class Domain(Base, VenusBase):
    __tablename__ = 'domains'
    deployed_at = Column(DateTime(32))
    deployment_manager = Column(String(50))
    published_at = Column(DateTime(32))
    state = Column(Enum('null', 'deploying', 'testing', 'product'))
    put = Column(JsonEncodedDict(1000))
    port_conf = Column(JsonEncodedDict(1000))
    raid_conf = Column(JsonEncodedDict(1000))
    networks = relationship('Network', back_populates='domain')

    @hybrid_property
    def sub_resources(self):
        return {'networks': self.networks}


class Network(Base, VenusBase):
    __tablename__ = 'networks'
    domain_uuid = Column(String(36), ForeignKey('domains.uuid'))
    type_ = Column('type', String(32))
    ip_range = Column(String(32))
    gateway = Column(String(32))
    netmask = Column(String(32))
    domain = relationship('Domain', back_populates='networks')


class Tag(Base, VenusBase):
    __tablename__ = 'tags'
    name = Column(String(32))
    type_ = Column('type', String(32))
    resource_type = Column(String(32))
    resource_uuid = Column(String(36))
