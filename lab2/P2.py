import os
import struct

PAGE_SIZE = 512

FILE_HEADER_FORMAT = '<ii'
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FORMAT)

class PageHeader:
  def __init__(self, num_slots=0, free_ptr=PAGE_SIZE, directorio=None):
    if directorio is None:
      directorio = []
    self.num_slots = num_slots
    self.free_ptr = free_ptr
    self.directorio = directorio

  def pack(self):
    data = struct.pack('<HH', self.num_slots, self.free_ptr)
    for offset, length in self.directorio:
      data += struct.pack('<hh', offset, length)
    return data

  @staticmethod
  def unpack(data):
    num_slots, free_ptr = struct.unpack_from('<HH', data, 0)
    directorio = []
    p = 4
    for _ in range(num_slots):
      offset, length = struct.unpack_from('<hh', data, p)
      directorio.append((offset, length))
      p += 4
    return PageHeader(num_slots, free_ptr, directorio)


class Matricula:
  def __init__(self, codigo, ciclo, mensualidad, observaciones):
    self.codigo = codigo
    self.ciclo = ciclo
    self.mensualidad = mensualidad
    self.observaciones = observaciones

  def pack(self):
    cod = self.codigo.encode()
    obs = self.observaciones.encode()
    return (struct.pack('<H', len(cod)) + cod +
            struct.pack('<if', self.ciclo, self.mensualidad) +
            struct.pack('<H', len(obs)) + obs)

  @staticmethod
  def unpack(data):
    p = 0
    (lc,) = struct.unpack_from('<H', data, p)
    p += 2
    codigo = data[p:p + lc].decode()
    p += lc
    ciclo, mensualidad = struct.unpack_from('<if', data, p)
    p += 8
    (lo,) = struct.unpack_from('<H', data, p)
    p += 2
    observaciones = data[p:p + lo].decode()
    p += lo
    return Matricula(codigo, ciclo, mensualidad, observaciones)

  def __repr__(self):
    return (f"Matricula({self.codigo!r}, {self.ciclo}, "
            f"{self.mensualidad}, {self.observaciones!r})")


class SlottedPage:
  def __init__(self, filename):
    self.filename = filename
    if not os.path.exists(self.filename):
      with open(self.filename, "wb") as f:
        f.write(struct.pack(FILE_HEADER_FORMAT, PAGE_SIZE, 0))

  def load(self):
    resultado = []
    with open(self.filename, "rb") as f:
      page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
      for page_id in range(num_pages):
        f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
        page = f.read(PAGE_SIZE)
        header = PageHeader.unpack(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
        for offset, length in header.directorio:
          if length == -1:
            continue
          record = Matricula.unpack(page[offset:offset + length])
          resultado.append(record)
    return resultado
    
  def add(self, record):
    pass

  def readRecord(self, rid):
    pass

  def remove(self, rid):
    pass

  def compact(self):
    pass

