import os
import struct

PAGE_SIZE = 512

FILE_HEADER_FORMAT = '<ii'
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FORMAT)


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


class Page:
  def __init__(self):
    self.num_slots = 0
    self.free_ptr = PAGE_SIZE
    self.directorio = []
    self.data = bytearray(PAGE_SIZE)

  def free_space(self):
    return self.free_ptr - (4 + self.num_slots * 4)

  def cabe(self, size):
    return self.free_space() >= size + 4

  def insert(self, record_bytes):
    size = len(record_bytes)
    offset = self.free_ptr - size
    self.data[offset:offset + size] = record_bytes
    slot_id = self.num_slots
    self.directorio.append((offset, size))
    self.num_slots += 1
    self.free_ptr = offset
    return slot_id

  def read(self, slot_id):
    if slot_id >= self.num_slots:
      return None
    offset, length = self.directorio[slot_id]
    if length == -1:
      return None
    return self.data[offset:offset + length]

  def delete(self, slot_id):
    if slot_id >= self.num_slots or self.directorio[slot_id][1] == -1:
      return
    self.directorio[slot_id] = (-1, -1)

  def pack(self):
    buf = bytearray(self.data)
    struct.pack_into('<HH', buf, 0, self.num_slots, self.free_ptr)
    off = 4
    for offset, length in self.directorio:
      struct.pack_into('<hh', buf, off, offset, length)
      off += 4
    return bytes(buf)

  @staticmethod
  def unpack(data):
    page = Page()
    page.data = bytearray(data)
    page.num_slots, page.free_ptr = struct.unpack_from('<HH', data, 0)
    off = 4
    for _ in range(page.num_slots):
      offset, length = struct.unpack_from('<hh', data, off)
      page.directorio.append((offset, length))
      off += 4
    return page


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
        page = Page.unpack(f.read(PAGE_SIZE))
        for slot_id in range(page.num_slots):
          record_bytes = page.read(slot_id)
          if record_bytes is not None:
            resultado.append(Matricula.unpack(record_bytes))
    return resultado

  def add(self, record):
    data = record.pack()
    size = len(data)
    with open(self.filename, "r+b") as f:
      page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
      for page_id in range(num_pages):
        f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
        page = Page.unpack(f.read(PAGE_SIZE))
        if page.cabe(size):
          slot_id = page.insert(data)
          f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
          f.write(page.pack())
          return (page_id, slot_id)

      page = Page()
      slot_id = page.insert(data)
      page_id = num_pages
      f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
      f.write(page.pack())
      f.seek(0)
      f.write(struct.pack(FILE_HEADER_FORMAT, PAGE_SIZE, num_pages + 1))
      return (page_id, slot_id)

  def readRecord(self, rid):
    page_id, slot_id = rid
    with open(self.filename, "rb") as f:
      page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
      if page_id >= num_pages:
        return None
      f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
      page = Page.unpack(f.read(PAGE_SIZE))
    record_bytes = page.read(slot_id)
    if record_bytes is None:
      return None
    return Matricula.unpack(record_bytes)

  def remove(self, rid):
    page_id, slot_id = rid
    with open(self.filename, "r+b") as f:
      page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
      if page_id >= num_pages:
        return
      f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
      page = Page.unpack(f.read(PAGE_SIZE))
      page.delete(slot_id)
      f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
      f.write(page.pack())

if __name__ == "__main__":
  def gen(i):
    obs = "obs " + "x" * (i % 40)
    return Matricula(f"M-{i:04}", (i % 10) + 1, 1000.0 + i, obs)

  def num_pages(fn):
    with open(fn, "rb") as f:
      return struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))[1]

  def page_meta(fn, p):
    with open(fn, "rb") as f:
      f.seek(FILE_HEADER_SIZE + p * PAGE_SIZE)
      page = Page.unpack(f.read(PAGE_SIZE))
    return page.num_slots, page.free_ptr, page.directorio

  N = 120
  fn = "matriculas.dat"
  if os.path.exists(fn):
    os.remove(fn)
  sp = SlottedPage(fn)

  rids = []
  for i in range(N):
    rids.append(sp.add(gen(i)))

  print("Registros insertados:", N)
  print("Numero de paginas:", num_pages(fn))
  print("RID reg 0:", rids[0])
  print("RID reg", N - 1, ":", rids[-1])
  print("load():", len(sp.load()), "registros")

  print("Tamano reg 0:", len(gen(0).pack()), "bytes")
  print("Tamano reg 50:", len(gen(50).pack()), "bytes")
  print("Tamano reg 119:", len(gen(119).pack()), "bytes")

  print("readRecord", rids[0], ":", sp.readRecord(rids[0]))
  print("readRecord", rids[50], ":", sp.readRecord(rids[50]))

  ns, fp, direc = page_meta(fn, 0)
  print("Pagina 0 antes -> num_slots:", ns, "free_ptr:", fp)
  print("Directorio pagina 0 antes:", direc)

  borrar = [rids[1], rids[3]]
  for rid in borrar:
    sp.remove(rid)
  print("remove:", borrar)

  ns, fp, direc = page_meta(fn, 0)
  print("Pagina 0 despues -> num_slots:", ns, "free_ptr:", fp)
  print("Directorio pagina 0 despues:", direc)
  print("readRecord", rids[1], "tras borrar:", sp.readRecord(rids[1]))
  print("load():", len(sp.load()), "registros")
