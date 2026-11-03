import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import heapq, itertools, struct, time, zipfile

MAGIC = b'HFC2'

# ---------------------------------------------------------------- algorithms
class Node:
    def __init__(self, freq, symbol=None, left=None, right=None):
        self.freq, self.symbol, self.left, self.right = freq, symbol, left, right

def merge_sort(items):
    """Merge sort on (symbol, frequency) pairs, highest frequency first."""
    if len(items) <= 1:
        return items[:]
    mid = len(items) // 2
    a, b = merge_sort(items[:mid]), merge_sort(items[mid:])
    result = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i][1] >= b[j][1]:
            result.append(a[i]); i += 1
        else:
            result.append(b[j]); j += 1
    return result + a[i:] + b[j:]

def build_tree(freq):
    counter = itertools.count()
    # sorted by symbol so the tree is identical when rebuilt during decompression
    heap = [(count, next(counter), Node(count, symbol=sym)) for sym, count in sorted(freq.items())]
    heapq.heapify(heap)
    if not heap:
        return None
    while len(heap) > 1:
        f1, _, left = heapq.heappop(heap)
        f2, _, right = heapq.heappop(heap)
        heapq.heappush(heap, (f1 + f2, next(counter), Node(f1 + f2, left=left, right=right)))
    return heap[0][2]

def dfs_codes(node, prefix='', codes=None):
    if codes is None:
        codes = {}
    if node is None:
        return codes
    if node.symbol is not None:
        codes[node.symbol] = prefix or '0'
    else:
        dfs_codes(node.left, prefix + '0', codes)
        dfs_codes(node.right, prefix + '1', codes)
    return codes

# ---------------------------------------------------------------- file format
# Stored inside the zip as compressed.dat. HFC2 payload: MAGIC | name_len(2) | name | original_size(8) | n_symbols(2) | n * (symbol(1) + freq(4)) | bits
def find_entry(archive):
    """Name of the entry inside the zip that holds the Huffman data (identified by its MAGIC bytes)."""
    for n in archive.namelist():
        with archive.open(n) as f:
            if f.read(4) == MAGIC:
                return n
    return None

def read_raw(source):
    """Returns the raw Huffman payload from a project .zip."""
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source, 'r') as archive:
            entry = find_entry(archive)
            if entry is None:
                raise ValueError('No compressed data found in archive')
            return archive.read(entry)
    return Path(source).read_bytes()

def parse_header(raw):
    if raw[:4] != MAGIC:
        raise ValueError('Not a valid HFC file (or made by an older version)')
    try:
        pos = 4
        name_len = struct.unpack_from('>H', raw, pos)[0]; pos += 2
        name = raw[pos:pos + name_len].decode('utf-8'); pos += name_len
        size, count = struct.unpack_from('>QH', raw, pos); pos += 10
        freq = {}
        for _ in range(count):
            sym, f = struct.unpack_from('>BI', raw, pos); pos += 5
            freq[sym] = f
    except (struct.error, UnicodeDecodeError):
        raise ValueError('Damaged file header')
    return Path(name).name, size, freq, pos

def is_compressed(path):
    """True if the file is a .zip produced by this program."""
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, 'r') as archive:
                return find_entry(archive) is not None
        with open(path, 'rb') as f:
            return f.read(4) == MAGIC
    except Exception:
        return False

def compress(source, target):
    data = Path(source).read_bytes()
    freq = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1
    if any(v >= 2**32 for v in freq.values()):
        raise ValueError('File too large')
    codes = dfs_codes(build_tree(freq))

    name = Path(source).name.encode('utf-8')
    header = bytearray(MAGIC)
    header += struct.pack('>H', len(name)) + name
    header += struct.pack('>QH', len(data), len(freq))
    for sym, f in sorted(freq.items()):
        header += struct.pack('>BI', sym, f)

    out = bytearray()
    buf = ''
    for i in range(0, len(data), 65536):
        buf += ''.join([codes[b] for b in data[i:i + 65536]])
        cut = len(buf) // 8 * 8
        if cut:
            out += int(buf[:cut], 2).to_bytes(cut // 8, 'big')
            buf = buf[cut:]
    if buf:
        buf += '0' * (8 - len(buf))
        out += int(buf, 2).to_bytes(1, 'big')

    payload = bytes(header) + bytes(out)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('compressed.dat', payload)
    return len(data), Path(target).stat().st_size, merge_sort(list(freq.items())), codes

def decompress(source, target):
    raw = read_raw(source)
    name, size, freq, start = parse_header(raw)
    if sum(freq.values()) != size:
        raise ValueError('Invalid frequency data')
    root = build_tree(freq)
    if size == 0:
        result = b''
    elif root.symbol is not None:
        result = bytes([root.symbol]) * size
    else:
        result = bytearray()
        node = root
        for byte in raw[start:]:
            for shift in range(7, -1, -1):
                node = node.right if (byte >> shift) & 1 else node.left
                if node is None:
                    raise ValueError('Invalid encoded data')
                if node.symbol is not None:
                    result.append(node.symbol)
                    if len(result) == size:
                        break
                    node = root
            if len(result) == size:
                break
        if len(result) != size:
            raise ValueError('Compressed data is incomplete')
    Path(target).write_bytes(result)
    return len(raw), len(result)

# ---------------------------------------------------------------- GUI
class App:
    def __init__(self, root):
        self.root = root; root.title('Huffman File Compression | DAA Mini Project'); root.geometry('900x650'); root.minsize(720, 520)
        root.configure(bg='#101827')
        style = ttk.Style(); style.theme_use('clam')
        style.configure('Treeview', background='#202d40', foreground='white', fieldbackground='#202d40', rowheight=26)
        style.configure('Treeview.Heading', background='#32445e', foreground='white', font=('Segoe UI', 10, 'bold'))
        tk.Label(root, text='HUFFMAN FILE COMPRESSION', font=('Segoe UI', 23, 'bold'), bg='#101827', fg='#65d6ff').pack(pady=(20, 3))
        tk.Label(root, text='Huffman Coding + DFS + Merge Sort', font=('Segoe UI', 12), bg='#101827', fg='#bdc9dc').pack(pady=(0, 16))
        bar = tk.Frame(root, bg='#101827'); bar.pack(fill='x', padx=28)
        self.path = tk.StringVar()
        tk.Entry(bar, textvariable=self.path, font=('Segoe UI', 11), bg='#202d40', fg='white', insertbackground='white', relief='flat').pack(side='left', fill='x', expand=True, ipady=10)
        tk.Button(bar, text='Browse File', command=self.browse, bg='#3b82f6', fg='white', relief='flat', font=('Segoe UI', 11, 'bold'), padx=18, pady=8).pack(side='left', padx=(8, 0))
        actions = tk.Frame(root, bg='#101827'); actions.pack(pady=16)
        for name, command, color in [('Compress', self.do_compress, '#16a34a'), ('Decompress', self.do_decompress, '#d97706'), ('Clear', self.clear, '#475569')]:
            tk.Button(actions, text=name, command=command, bg=color, fg='white', relief='flat', font=('Segoe UI', 11, 'bold'), width=15, pady=10).pack(side='left', padx=7)
        self.status = tk.StringVar(value='Choose a file. A compressed .zip from this program is decompressed automatically.')
        tk.Label(root, textvariable=self.status, bg='#101827', fg='#e2e8f0', font=('Segoe UI', 10), wraplength=800).pack(padx=20, pady=(0, 10))
        tk.Label(root, text='CHARACTER / BYTE FREQUENCY (MERGE SORT: HIGHEST FIRST)', bg='#101827', fg='#65d6ff', font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=30, pady=(8, 5))
        frame = tk.Frame(root, bg='#101827'); frame.pack(fill='both', expand=True, padx=30, pady=(0, 12))
        self.table = ttk.Treeview(frame, columns=('symbol', 'freq', 'code'), show='headings')
        for col, title, width in [('symbol', 'Byte / Character', 230), ('freq', 'Frequency', 170), ('code', 'Huffman Code (DFS)', 340)]:
            self.table.heading(col, text=title); self.table.column(col, width=width)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.table.yview); self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left', fill='both', expand=True); scroll.pack(side='right', fill='y')
        tk.Label(root, text='Lossless compression • Original file is never overwritten • ZIP archive containing Huffman encoded data', bg='#101827', fg='#94a3b8').pack(pady=(0, 12))

    def browse(self):
        file = filedialog.askopenfilename(title='Select a file')
        if not file:
            return
        self.path.set(file)
        if is_compressed(file):
            self.status.set('Compressed file detected - decompressing...')
            self.root.after(100, self.do_decompress)   # auto-decompress on select
        else:
            self.status.set('File selected. Click Compress.')

    def clear(self):
        self.path.set(''); self.status.set('Choose a file to begin.'); self.table.delete(*self.table.get_children())

    def do_compress(self):
        source = self.path.get()
        if not Path(source).is_file():
            messagebox.showwarning('File required', 'Choose an existing file.'); return
        if is_compressed(source):
            messagebox.showinfo('Already compressed', 'This file is already compressed. Use Decompress.'); return
        target = filedialog.asksaveasfilename(defaultextension='.zip', initialfile=Path(source).name + '.zip', filetypes=[('ZIP files', '*.zip')])
        if not target: return
        if not target.lower().endswith('.zip'):
            target += '.zip'
        if Path(source).resolve() == Path(target).resolve():
            messagebox.showerror('Error', 'Output must differ from input.'); return
        try:
            start = time.perf_counter(); original, packed, sorted_items, codes = compress(source, target)
            self.table.delete(*self.table.get_children())
            for sym, freq in sorted_items:
                name = repr(chr(sym)) if 32 <= sym <= 126 else f'0x{sym:02X}'
                self.table.insert('', 'end', values=(f'{sym} ({name})', freq, codes[sym]))
            saving = (1 - packed / original) * 100 if original else 0
            msg = f'Compressed! {original:,} → {packed:,} bytes | Space saving: {saving:.2f}% | Time: {time.perf_counter()-start:.3f}s'
            if packed >= original:
                msg += '  (This file is too small or already compressed, e.g. JPG/MP4/ZIP, so Huffman cannot shrink it.)'
            self.status.set(msg)
            messagebox.showinfo('Success', f'Compressed file saved:\n{target}')
        except Exception as exc:
            messagebox.showerror('Compression failed', str(exc))

    def do_decompress(self):
        source = self.path.get()
        if not Path(source).is_file():
            messagebox.showwarning('File required', 'Choose an existing compressed file.'); return
        if not is_compressed(source):
            messagebox.showerror('Invalid file', 'This file was not created by this program.'); return
        try:
            name = parse_header(read_raw(source))[0]
        except Exception as exc:
            messagebox.showerror('Invalid archive', str(exc)); return
        suffix = Path(name).suffix
        types = [(f'{suffix} files', f'*{suffix}'), ('All files', '*.*')] if suffix else [('All files', '*.*')]
        target = filedialog.asksaveasfilename(initialfile=name or 'restored_file', defaultextension=suffix,
                                              filetypes=types, title='Save restored file')
        if not target: return
        if Path(source).resolve() == Path(target).resolve():
            messagebox.showerror('Error', 'Output must differ from input.'); return
        try:
            start = time.perf_counter(); compressed, restored = decompress(source, target)
            self.status.set(f'Decompressed! {compressed:,} → {restored:,} bytes | Time: {time.perf_counter()-start:.3f}s')
            messagebox.showinfo('Success', f'Original file restored:\n{target}')
        except Exception as exc:
            messagebox.showerror('Decompression failed', str(exc))

if __name__ == '__main__':
    root = tk.Tk(); App(root); root.mainloop()