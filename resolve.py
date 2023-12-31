from dataclasses import dataclass
from io import BytesIO
from typing import List
import dataclasses
import socket
import struct
import sys
import random

TYPE_A = 1
TYPE_NS = 2
TYPE_TXT = 16
CLASS_IN = 1


@dataclass
class DNSHeader:
    id: int
    flags: int
    num_questions: int = 0
    num_answers: int = 0
    num_authorities: int = 0
    num_additionals: int = 0


@dataclass
class DNSQuestion:
    name: bytes
    type_: int
    class_: int


@dataclass
class DNSRecord:
    name: bytes
    type_: int
    class_: int
    ttl: int
    data: bytes


@dataclass
class DNSPacket:
    header: DNSHeader
    questions: List[DNSQuestion]
    answers: List[DNSRecord]
    authorities: List[DNSRecord]
    additionals: List[DNSRecord]


def header_to_bytes(header):
    fields = dataclasses.astuple(header)
    # there are 6 `H`s because there are 6 fields
    return struct.pack("!HHHHHH", *fields)


def question_to_bytes(question):
    return question.name + struct.pack("!HH", question.type_, question.class_)


def encode_dns_name(domain_name):
    encoded = b""
    for part in domain_name.encode("ascii").split(b"."):
        encoded += bytes([len(part)]) + part
    return encoded + b"\x00"


def build_query(domain_name, record_type):
    name = encode_dns_name(domain_name)
    id = random.randint(0, 65535)
    header = DNSHeader(id=id, num_questions=1, flags=0)
    question = DNSQuestion(name=name, type_=record_type, class_=CLASS_IN)
    return header_to_bytes(header) + question_to_bytes(question)


def send_query(ip_address, domain_name, record_type):
    query = build_query(domain_name, record_type)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(query, (ip_address, 53))

    data, _ = sock.recvfrom(1024)
    return parse_dns_packet(data)


def parse_header(reader):
    items = struct.unpack("!HHHHHH", reader.read(12))
    # see "a note on BytesIO" for an explanation of `reader` here
    return DNSHeader(*items)


def decode_name_simple(reader):
    parts = []
    while (length := reader.read(1)[0]) != 0:
        parts.append(reader.read(length))
    return b".".join(parts)


def parse_question(reader):
    name = decode_name_simple(reader)
    data = reader.read(4)
    type_, class_ = struct.unpack("!HH", data)
    return DNSQuestion(name, type_, class_)


def decode_name(reader):
    parts = []
    while (length := reader.read(1)[0]) != 0:
        if length & 0b1100_0000:
            parts.append(decode_compressed_name(length, reader))
            break
        else:
            parts.append(reader.read(length))
    return b".".join(parts)


def decode_compressed_name(length, reader):
    pointer_bytes = bytes([length & 0b0011_1111]) + reader.read(1)
    pointer = struct.unpack("!H", pointer_bytes)[0]
    current_pos = reader.tell()
    reader.seek(pointer)
    result = decode_name(reader)
    reader.seek(current_pos)
    return result


def parse_record(reader):
    name = decode_name(reader)
    # the type, class, TTL, and data length together are 10 bytes (2 + 2 + 4 + 2 = 10)
    # so we read 10 bytes
    data = reader.read(10)
    # HHIH means 2-byte int, 2-byte-int, 4-byte int, 2-byte int
    type_, class_, ttl, data_len = struct.unpack("!HHIH", data)
    # It would be more hygienic here to store the raw data and the
    # parsed result in separate fields in DNSRecord, but we're lazy
    if type_ == TYPE_NS:
        data = decode_name(reader)
    elif type_ == TYPE_A:
        data = ip_to_string(reader.read(data_len))
    else:
        data = reader.read(data_len)
    return DNSRecord(name, type_, class_, ttl, data)


def parse_dns_packet(data):
    reader = BytesIO(data)
    header = parse_header(reader)
    questions = [parse_question(reader) for _ in range(header.num_questions)]
    answers = [parse_record(reader) for _ in range(header.num_answers)]
    authorities = [parse_record(reader) for _ in range(header.num_authorities)]
    additionals = [parse_record(reader) for _ in range(header.num_additionals)]

    return DNSPacket(header, questions, answers, authorities, additionals)

def ip_to_string(ip):
    return ".".join([str(x) for x in ip])

def lookup_domain(domain_name):
    query = build_query(domain_name, TYPE_A)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(query, ("8.8.8.8", 53))

    # get the response
    data, _ = sock.recvfrom(1024)
    response = parse_dns_packet(data)
    return ip_to_string(response.answers[0].data)


def get_answer(packet):
    # return the first A record in the Answer section
    for x in packet.answers:
            if x.type_ == TYPE_A:
                return x.data


def get_nameserver_ip(packet):
    # return the first A record in the Additional section
    for x in packet.additionals:
        if x.type_ == TYPE_A:
            return x.data


def get_nameserver(packet):
    # return the first NS record in the Authority section
    for x in packet.additionals:
        if x.type_ == TYPE_NS:
            return x.data.decode('utf-8')


def resolve(domain_name, record_type):
    nameserver = "198.41.0.4"
    while True:
        print(f"Querying {nameserver} for {domain_name}")
        response = send_query(nameserver, domain_name, record_type)
        if ip := get_answer(response):
            return ip
        elif nsIP := get_nameserver_ip(response):
            nameserver = nsIP
        # New case: look up the nameserver's IP address if there is one
        elif ns_domain := get_nameserver(response):
            nameserver = resolve(ns_domain, TYPE_A)
        else:
            raise Exception("something went wrong")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(resolve(sys.argv[1], TYPE_A))
    else:
        print("usage: python3 resolve.py <domain>")
        sys.exit(1)
