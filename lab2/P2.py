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
        header = PageHeader.unpack(page)
        for offset, length in header.directorio:
          if length == -1:
            continue
          record = Matricula.unpack(page[offset:offset + length])
          resultado.append(record)
    return resultado

  def add(self, record):
    data = record.pack()
    size = len(data)
    with open(self.filename, "r+b") as f:
      page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))

      page_id = -1
      page = None
      header = None
      for p in range(num_pages):
        f.seek(FILE_HEADER_SIZE + p * PAGE_SIZE)
        page = bytearray(f.read(PAGE_SIZE))
        header = PageHeader.unpack(page)
        free_space = header.free_ptr - (4 + header.num_slots * 4)
        if free_space >= size + 4:
          page_id = p
          break

      if page_id == -1:
        page_id = num_pages
        page = bytearray(PAGE_SIZE)
        header = PageHeader()
        num_pages += 1
        f.seek(0)
        f.write(struct.pack(FILE_HEADER_FORMAT, page_size, num_pages))

      slot_id = header.num_slots
      offset = header.free_ptr - size
      page[offset:offset + size] = data
      header.directorio.append((offset, size))
      header.num_slots += 1
      header.free_ptr = offset

      hb = header.pack()
      page[0:len(hb)] = hb
      f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
      f.write(page)

    return (page_id, slot_id)

  def readRecord(self, rid):
    page_id, slot_id = rid
    with open(self.filename, "rb") as f:
      page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
      if page_id >= num_pages:
        return None
      f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
      page = f.read(PAGE_SIZE)
    header = PageHeader.unpack(page)
    if slot_id >= header.num_slots:
      return None
    offset, length = header.directorio[slot_id]
    if length == -1:
      return None
    return Matricula.unpack(page[offset:offset + length])

  def remove(self, rid):
    page_id, slot_id = rid
    with open(self.filename, "r+b") as f:
      page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
      if page_id >= num_pages:
        return
      f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
      page = bytearray(f.read(PAGE_SIZE))
      header = PageHeader.unpack(page)
      if slot_id >= header.num_slots or header.directorio[slot_id][1] == -1:
        return
      header.directorio[slot_id] = (-1, -1)
      hb = header.pack()
      page[0:len(hb)] = hb
      f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
      f.write(page)


if __name__ == "__main__":
  def gen(i):
    obs = "obs " + "x" * (i % 40)
    return Matricula(f"M-{i:04}", (i % 10) + 1, 1000.0 + i, obs)

  def file_header(fn):
    with open(fn, "rb") as f:
      return struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))

  def page_header(fn, p):
    with open(fn, "rb") as f:
      f.seek(FILE_HEADER_SIZE + p * PAGE_SIZE)
      page = f.read(PAGE_SIZE)
    h = PageHeader.unpack(page)
    return h.num_slots, h.free_ptr, h.directorio

  N = 120
  fn = "matriculas.dat"
  if os.path.exists(fn):
    os.remove(fn)
  sp = SlottedPage(fn)

  rids = []
  for i in range(N):
    rids.append(sp.add(gen(i)))

  ps, npg = file_header(fn)
  print("Registros insertados:", N)
  print("Numero de paginas:", npg)
  print("RID reg 0:", rids[0])
  print("RID reg", N - 1, ":", rids[-1])
  print("load():", len(sp.load()), "registros")

  print("Tamano reg 0:", len(gen(0).pack()), "bytes")
  print("Tamano reg 50:", len(gen(50).pack()), "bytes")
  print("Tamano reg 119:", len(gen(119).pack()), "bytes")

  print("readRecord", rids[0], ":", sp.readRecord(rids[0]))
  print("readRecord", rids[50], ":", sp.readRecord(rids[50]))

  ns, fp, direc = page_header(fn, 0)
  print("Pagina 0 antes -> num_slots:", ns, "free_ptr:", fp)
  print("Directorio pagina 0 antes:", direc)

  borrar = [rids[1], rids[3]]
  for rid in borrar:
    sp.remove(rid)
  print("remove:", borrar)

  ns, fp, direc = page_header(fn, 0)
  print("Pagina 0 despues -> num_slots:", ns, "free_ptr:", fp)
  print("Directorio pagina 0 despues:", direc)
  print("readRecord", rids[1], "tras borrar:", sp.readRecord(rids[1]))
  print("load():", len(sp.load()), "registros")



