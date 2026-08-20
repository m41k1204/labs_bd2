import os
import struct


PAGE_SIZE = 512

FORMAT = '<5s11s20s15sif'
RECORD_SIZE = struct.calcsize(FORMAT)

FILE_HEADER_FORMAT = '<ii'
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FORMAT)

PAGE_HEADER_FORMAT = '<iii'
PAGE_HEADER_SIZE = struct.calcsize(PAGE_HEADER_FORMAT)

SLOT_SIZE = 1 + RECORD_SIZE

SLOTS_PER_PAGE = (PAGE_SIZE - PAGE_HEADER_SIZE) // SLOT_SIZE

ACTIVO = b'\x01'
BORRADO = b'\x00'

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

def leerRegistroBinario(filename, pos):
    with open(filename, "rb") as file:
        file.seek(pos * RECORD_SIZE)
        data = file.read(RECORD_SIZE)
        if not data:
            return None
        codigo, nombre, apellido, carrera, ciclo, mensualidad = struct.unpack(FORMAT, data)
        return Alumno(codigo.decode().strip('\x00'), nombre.decode().strip('\x00'),
                      apellido.decode().strip('\x00'), carrera.decode().strip('\x00'),
                      ciclo, mensualidad)


class FixedRecord:
    def __init__(self, filename, modo=MOVE_LAST):
        self.filename = filename
        self.modo = modo
        if not os.path.exists(self.filename):
            with open(self.filename, "wb") as f:
                f.write(struct.pack(FILE_HEADER_FORMAT, PAGE_SIZE, 0))
        else:
            with open(self.filename, "rb") as f:
                self.page_size, self.num_pages = struct.unpack(
                    FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))

    def load(self):
        resultado = []
        with open(self.filename, "rb") as f:
            page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
            for page_id in range(num_pages):
                f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
                total, activos, free_pointer = struct.unpack(PAGE_HEADER_FORMAT, f.read(PAGE_HEADER_SIZE))
                for slot_id in range(total):
                    offset = (FILE_HEADER_SIZE + page_id * PAGE_SIZE
                              + PAGE_HEADER_SIZE + slot_id * SLOT_SIZE)
                    f.seek(offset)
                    flag = f.read(1)
                    data = f.read(RECORD_SIZE)
                    if flag != ACTIVO:
                        continue
                    codigo, nombre, apellido, carrera, ciclo, mensualidad = struct.unpack(FORMAT, data)
                    resultado.append(Alumno(codigo.decode().strip('\x00'), nombre.decode().strip('\x00'),
                                            apellido.decode().strip('\x00'), carrera.decode().strip('\x00'),
                                            ciclo, mensualidad))
        return resultado

    def add(self, record):
        data = struct.pack(FORMAT, record.codigo.encode(), record.nombre.encode(),
                           record.apellido.encode(), record.carrera.encode(),
                           record.ciclo, record.mensualidad)
        with open(self.filename, "r+b") as f:
            page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))

            if self.modo == FREE_LIST:
                for p in range(num_pages):
                    page_header_off = FILE_HEADER_SIZE + p * PAGE_SIZE
                    f.seek(page_header_off)
                    total, activos, free_pointer = struct.unpack(PAGE_HEADER_FORMAT, f.read(PAGE_HEADER_SIZE))
                    if free_pointer != -1:
                        slot_id = free_pointer
                        slot_off = page_header_off + PAGE_HEADER_SIZE + slot_id * SLOT_SIZE
                        f.seek(slot_off + 1)
                        (next_free,) = struct.unpack('<i', f.read(4))
                        f.seek(slot_off)
                        f.write(ACTIVO + data)
                        f.seek(page_header_off)
                        f.write(struct.pack(PAGE_HEADER_FORMAT, total, activos + 1, next_free))
                        return (p, slot_id)

            page_id = -1
            total = activos = 0
            free_pointer = -1
            for p in range(num_pages):
                f.seek(FILE_HEADER_SIZE + p * PAGE_SIZE)
                total, activos, free_pointer = struct.unpack(PAGE_HEADER_FORMAT, f.read(PAGE_HEADER_SIZE))
                if total < SLOTS_PER_PAGE:
                    page_id = p
                    break

            if page_id == -1:
                page_id = num_pages
                total = activos = 0
                free_pointer = -1
                f.seek(0, 2)
                f.write(struct.pack(PAGE_HEADER_FORMAT, total, activos, free_pointer))
                f.write(b'\x00' * (PAGE_SIZE - PAGE_HEADER_SIZE))
                num_pages += 1
                f.seek(0)
                f.write(struct.pack(FILE_HEADER_FORMAT, page_size, num_pages))

            slot_id = total
            offset = FILE_HEADER_SIZE + page_id * PAGE_SIZE + PAGE_HEADER_SIZE + slot_id * SLOT_SIZE
            f.seek(offset)
            f.write(ACTIVO + data)

            f.seek(FILE_HEADER_SIZE + page_id * PAGE_SIZE)
            f.write(struct.pack(PAGE_HEADER_FORMAT, total + 1, activos + 1, free_pointer))

        return (page_id, slot_id)

    def readRecord(self, rid):
        page_id, slot_id = rid
        offset = FILE_HEADER_SIZE + page_id * PAGE_SIZE + PAGE_HEADER_SIZE + slot_id * SLOT_SIZE
        with open(self.filename, "rb") as f:
            f.seek(offset)
            flag = f.read(1)
            data = f.read(RECORD_SIZE)
            if flag != ACTIVO:
                return None
            codigo, nombre, apellido, carrera, ciclo, mensualidad = struct.unpack(FORMAT, data)
            return Alumno(codigo.decode().strip('\x00'), nombre.decode().strip('\x00'),
                          apellido.decode().strip('\x00'), carrera.decode().strip('\x00'),
                          ciclo, mensualidad)

    def remove(self, rid):
        if self.modo == MOVE_LAST:
            self._remove_move_last(rid)
        else:
            self._remove_free_list(rid)

    def _remove_move_last(self, rid):
        page_id, slot_id = rid
        with open(self.filename, "r+b") as f:
            page_size, num_pages = struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))
            if num_pages == 0 or page_id >= num_pages:
                return

            tp_off = FILE_HEADER_SIZE + page_id * PAGE_SIZE
            f.seek(tp_off)
            tt, ta, tf = struct.unpack(PAGE_HEADER_FORMAT, f.read(PAGE_HEADER_SIZE))
            if slot_id >= tt:
                return

            last_page = num_pages - 1
            lp_off = FILE_HEADER_SIZE + last_page * PAGE_SIZE
            f.seek(lp_off)
            lt, la, lf = struct.unpack(PAGE_HEADER_FORMAT, f.read(PAGE_HEADER_SIZE))
            last_slot = lt - 1
            last_slot_off = lp_off + PAGE_HEADER_SIZE + last_slot * SLOT_SIZE
            f.seek(last_slot_off)
            last_bytes = f.read(SLOT_SIZE)

            if (page_id, slot_id) != (last_page, last_slot):
                target_off = FILE_HEADER_SIZE + page_id * PAGE_SIZE + PAGE_HEADER_SIZE + slot_id * SLOT_SIZE
                f.seek(target_off)
                f.write(last_bytes)

            f.seek(lp_off)
            f.write(struct.pack(PAGE_HEADER_FORMAT, lt - 1, la - 1, lf))

            if lt - 1 == 0:
                f.truncate(lp_off)
                f.seek(0)
                f.write(struct.pack(FILE_HEADER_FORMAT, page_size, num_pages - 1))

    def _remove_free_list(self, rid):
        page_id, slot_id = rid
        page_header_off = FILE_HEADER_SIZE + page_id * PAGE_SIZE
        slot_off = page_header_off + PAGE_HEADER_SIZE + slot_id * SLOT_SIZE
        with open(self.filename, "r+b") as f:
            f.seek(page_header_off)
            total, activos, free_pointer = struct.unpack(PAGE_HEADER_FORMAT, f.read(PAGE_HEADER_SIZE))
            f.seek(slot_off)
            if f.read(1) != ACTIVO:
                return
            f.seek(slot_off)
            f.write(BORRADO + struct.pack('<i', free_pointer))
            f.seek(page_header_off)
            f.write(struct.pack(PAGE_HEADER_FORMAT, total, activos - 1, slot_id))


if __name__ == "__main__":
    def gen(i):
        return Alumno(f"{i:05}", f"Nom{i}", f"Ape{i}",
                      ["Computacion", "Industrial", "Mecatronica"][i % 3],
                      (i % 10) + 1, 1500.0 + i)

    def file_header(fn):
        with open(fn, "rb") as f:
            return struct.unpack(FILE_HEADER_FORMAT, f.read(FILE_HEADER_SIZE))

    def page_header(fn, p):
        with open(fn, "rb") as f:
            f.seek(FILE_HEADER_SIZE + p * PAGE_SIZE)
            return struct.unpack(PAGE_HEADER_FORMAT, f.read(PAGE_HEADER_SIZE))

    N = 120
    print("\nESTRATEGIA FREE LIST")
    fn = "alumnos_freelist.dat"
    if os.path.exists(fn):
        os.remove(fn)
    fr = FixedRecord(fn, FREE_LIST)
    rids = [fr.add(gen(i)) for i in range(N)]
    ps, npg = file_header(fn)
    print(f"\nInsertados {N} registros {npg} paginas (creacion automatica de paginas)")
    print(f"RID reg 0   : {rids[0]}")
    print(f"RID reg 8   : {rids[8]}   (arranca pagina 1)")
    print(f"RID reg {N-1} : {rids[-1]}")
    print(f"load() devuelve {len(fr.load())} registros")

    print("\nLectura por RID:")
    print(f"readRecord({rids[8]})  = {fr.readRecord(rids[8])}")
    print(f"readRecord({rids[50]}) = {fr.readRecord(rids[50])}")

    print("\nHeaders de paginas 0 y 1 ANTES de borrar:")
    for p in range(2):
        print(f"pagina {p}: {page_header(fn, p)}  (total, activos, free_pointer)")

    borrar = [(0, 2), (0, 5), (1, 0)]
    for rid in borrar:
        fr.remove(rid)
    print(f"\nremove {borrar}")
    print("Headers DESPUES (total igual, activos baja, free_pointer = ultimo borrado):")
    for p in range(2):
        print(f"pagina {p}: {page_header(fn, p)}")
    print(f"load() ahora devuelve {len(fr.load())} registros (sin los borrados)")
    print(f"readRecord((0,2)) = {fr.readRecord((0, 2))}")

    print("\nReinsercion (debe REUSAR los slots liberados):")
    for k in range(3):
        nuevo = fr.add(gen(1000 + k))
        print(f"add RID {nuevo}   (slot reciclado)")
    print(f"load() vuelve a {len(fr.load())} registros")

    print("\n\nESTRATEGIA MOVE THE LAST")
    fn2 = "alumnos_movelast.dat"
    if os.path.exists(fn2):
        os.remove(fn2)
    ml = FixedRecord(fn2, MOVE_LAST)
    rids2 = [ml.add(gen(i)) for i in range(N)]
    ps, npg = file_header(fn2)
    print(f"\nInsertados {N} registros {npg} paginas")
    print(f"Ultimo registro global: {ml.readRecord(rids2[-1]).codigo} en RID {rids2[-1]}")

    print("\nremove((0,3)) : el ultimo global se mueve a (0,3)")
    ultima_ini = npg - 1
    print("Headers ANTES:")
    print(f"pagina 0    : {page_header(fn2, 0)}  (total, activos, free_pointer)")
    print(f"pagina {ultima_ini} (ultima): {page_header(fn2, ultima_ini)}")
    print(f"(0,3) = {ml.readRecord((0, 3)).codigo}")
    ml.remove((0, 3))
    print("Headers DESPUES (pagina 0 igual, ultima pagina encoge su total):")
    print(f"pagina 0    : {page_header(fn2, 0)}")
    print(f"pagina {ultima_ini} (ultima): {page_header(fn2, ultima_ini)}")
    print(f"(0,3) = {ml.readRecord((0, 3)).codigo} se movio el ultimo")
    print(f"load() = {len(ml.load())} registros")

    print("\nVaciar la ultima pagina para ver TRUNCACION:")
    ps, npg = file_header(fn2)
    ultima = npg - 1
    total_ultima = page_header(fn2, ultima)[0]
    print(f"num_pages antes: {npg}, filesize: {os.path.getsize(fn2)} bytes")
    for _ in range(total_ultima):
        ml.remove((ultima, 0))
    ps, npg = file_header(fn2)
    print(f"num_pages despues: {npg}, filesize: {os.path.getsize(fn2)} bytes (pagina vacia truncada)")
    print(f"load() = {len(ml.load())} registros")
