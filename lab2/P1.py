import os
import struct


PAGE_SIZE = 512

FORMAT = '<5s11s20s15sif'
RECORD_SIZE = struct.calcsize(FORMAT)

FILE_HEADER_FORMAT = '<ii'
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FORMAT)

PAGE_HEADER_FORMAT = '<ii'
PAGE_HEADER_SIZE = struct.calcsize(PAGE_HEADER_FORMAT)

SLOT_SIZE = 1 + RECORD_SIZE

SLOTS_PER_PAGE = (PAGE_SIZE - PAGE_HEADER_SIZE) // SLOT_SIZE

MOVE_LAST = "move_last"
FREE_LIST = "free_list"


class Alumno:
    def __init__(self, codigo, nombre, apellido, carrera, ciclo, mensualidad):
        self.codigo = codigo
        self.nombre = nombre
        self.apellido = apellido
        self.carrera = carrera
        self.ciclo = ciclo
        self.mensualidad = mensualidad

    def __repr__(self):
        return (f"Alumno({self.codigo!r}, {self.nombre!r}, {self.apellido!r}, "
                f"{self.carrera!r}, {self.ciclo}, {self.mensualidad})")


class Page:
    def __init__(self):
        self.num_records = 0
        self.head_free_list = -1
        self.records = []

    def hay_espacio(self):
        return self.num_records < SLOTS_PER_PAGE

    def hay_libre(self):
        return self.head_free_list != -1

    def pack(self):
        buf = bytearray(PAGE_SIZE)
        struct.pack_into(PAGE_HEADER_FORMAT, buf, 0, self.num_records, self.head_free_list)
        off = PAGE_HEADER_SIZE
        for slot in self.records:
            if isinstance(slot, Alumno):
                buf[off] = 1
                struct.pack_into(FORMAT, buf, off + 1,
                                 slot.codigo.encode(), slot.nombre.encode(),
                                 slot.apellido.encode(), slot.carrera.encode(),
                                 slot.ciclo, slot.mensualidad)
            else:
                buf[off] = 0
                struct.pack_into('<i', buf, off + 1, slot)
            off += SLOT_SIZE
        return bytes(buf)

    @staticmethod
    def unpack(data):
        page = Page()
        page.num_records, page.head_free_list = struct.unpack_from(PAGE_HEADER_FORMAT, data, 0)
        off = PAGE_HEADER_SIZE
        for _ in range(page.num_records):
            flag = data[off]
            if flag == 1:
                codigo, nombre, apellido, carrera, ciclo, mensualidad = struct.unpack_from(FORMAT, data, off + 1)
                page.records.append(Alumno(codigo.decode().strip('\x00'), nombre.decode().strip('\x00'),
                                           apellido.decode().strip('\x00'), carrera.decode().strip('\x00'),
                                           ciclo, mensualidad))
            else:
                (next_free,) = struct.unpack_from('<i', data, off + 1)
                page.records.append(next_free)
            off += SLOT_SIZE
        return page


class FixedRecord:
    def __init__(self, filename, modo=MOVE_LAST):
        self.filename = filename
        self.modo = modo
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
                for slot in page.records:
                    if isinstance(slot, Alumno):
                        resultado.append(slot)
        return resultado

    def add(self, record):
        with open(self.filename, "r+b") as f:
            page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))

            if self.modo == FREE_LIST:
                for page_id in range(num_pages):
                    f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
                    page = Page.unpack(f.read(PAGE_SIZE))
                    if page.hay_libre():
                        slot_id = page.head_free_list
                        page.head_free_list = page.records[slot_id]
                        page.records[slot_id] = record
                        f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
                        f.write(page.pack())
                        return (page_id, slot_id)

            for page_id in range(num_pages):
                f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
                page = Page.unpack(f.read(PAGE_SIZE))
                if page.hay_espacio():
                    slot_id = page.num_records
                    page.records.append(record)
                    page.num_records += 1
                    f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
                    f.write(page.pack())
                    return (page_id, slot_id)

            page = Page()
            page.records.append(record)
            page.num_records = 1
            page_id = num_pages
            f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
            f.write(page.pack())
            f.seek(0)
            f.write(struct.pack(FILE_HEADER_FORMAT, PAGE_SIZE, num_pages + 1))
            return (page_id, 0)

    def readRecord(self, rid):
        page_id, slot_id = rid
        with open(self.filename, "rb") as f:
            page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
            if page_id >= num_pages:
                return None
            f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
            page = Page.unpack(f.read(PAGE_SIZE))
        if slot_id >= page.num_records:
            return None
        slot = page.records[slot_id]
        if isinstance(slot, Alumno):
            return slot
        return None

    def remove(self, rid):
        if self.modo == MOVE_LAST:
            self._remove_move_last(rid)
        else:
            self._remove_free_list(rid)

    def _remove_free_list(self, rid):
        page_id, slot_id = rid
        with open(self.filename, "r+b") as f:
            page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
            if page_id >= num_pages:
                return
            f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
            page = Page.unpack(f.read(PAGE_SIZE))
            if slot_id >= page.num_records or not isinstance(page.records[slot_id], Alumno):
                return
            page.records[slot_id] = page.head_free_list
            page.head_free_list = slot_id
            f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
            f.write(page.pack())

    def _remove_move_last(self, rid):
        page_id, slot_id = rid
        with open(self.filename, "r+b") as f:
            page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
            if page_id >= num_pages:
                return
            f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
            page = Page.unpack(f.read(PAGE_SIZE))
            if slot_id >= page.num_records:
                return
            last = page.num_records - 1
            if slot_id != last:
                page.records[slot_id] = page.records[last]
            page.records.pop()
            page.num_records -= 1
            f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
            f.write(page.pack())


if __name__ == "__main__":
    def gen(i):
        return Alumno(f"{i:05}", f"Nom{i}", f"Ape{i}",
                      ["Computacion", "Industrial", "Mecatronica"][i % 3],
                      (i % 10) + 1, 1500.0 + i)

    def num_pages(fn):
        with open(fn, "rb") as f:
            return struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))[1]

    def page_meta(fn, p):
        with open(fn, "rb") as f:
            f.seek(FILE_HEADER_SIZE + p * PAGE_SIZE)
            page = Page.unpack(f.read(PAGE_SIZE))
        return page.num_records, page.head_free_list

    N = 120

    print("ESTRATEGIA FREE LIST")
    fn = "alumnos_freelist.dat"
    if os.path.exists(fn):
        os.remove(fn)
    fr = FixedRecord(fn, FREE_LIST)
    rids = []
    for i in range(N):
        rids.append(fr.add(gen(i)))
    print("Registros insertados:", N)
    print("Numero de paginas:", num_pages(fn))
    print("RID reg 0:", rids[0])
    print("RID reg 8:", rids[8])
    print("RID reg", N - 1, ":", rids[-1])
    print("load():", len(fr.load()), "registros")
    print("readRecord", rids[8], ":", fr.readRecord(rids[8]))
    print("Pagina 0 antes (num_records, head_free_list):", page_meta(fn, 0))
    borrar = [(0, 2), (0, 5)]
    for rid in borrar:
        fr.remove(rid)
    print("remove:", borrar)
    print("Pagina 0 despues (num_records, head_free_list):", page_meta(fn, 0))
    print("load():", len(fr.load()), "registros")
    print("readRecord (0,2):", fr.readRecord((0, 2)))
    print("Reinsercion:")
    for k in range(2):
        print("add RID:", fr.add(gen(1000 + k)))
    print("load():", len(fr.load()), "registros")

    print("ESTRATEGIA MOVE THE LAST")
    fn2 = "alumnos_movelast.dat"
    if os.path.exists(fn2):
        os.remove(fn2)
    ml = FixedRecord(fn2, MOVE_LAST)
    rids2 = []
    for i in range(N):
        rids2.append(ml.add(gen(i)))
    print("Registros insertados:", N)
    print("Numero de paginas:", num_pages(fn2))
    print("Pagina 0 antes (num_records, head_free_list):", page_meta(fn2, 0))
    print("(0,3) antes:", ml.readRecord((0, 3)).codigo)
    ml.remove((0, 3))
    print("remove: (0, 3)")
    print("Pagina 0 despues (num_records, head_free_list):", page_meta(fn2, 0))
    print("(0,3) despues:", ml.readRecord((0, 3)).codigo)
    print("load():", len(ml.load()), "registros")
