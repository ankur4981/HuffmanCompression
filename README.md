# Huffman File Compression (ZIP) — DAA Mini Project

Algorithms: Huffman Coding (greedy), DFS (tree traversal for codes), Merge Sort (frequency display).

## Run
`python main.py` (Python 3, Tkinter included with most installations).

## Compress
Browse any file, click **Compress**, and save a `.zip` archive. The ZIP contains `compressed.hfc` (actual Huffman-coded data) and `metadata.json` (original filename). This is a valid ZIP archive and can be opened by ZIP tools, but the `.hfc` member needs this project to decode.

## Decompress
Browse a `.zip` created by this application, click **Decompress**, and choose where to save the restored original file. Other ordinary ZIP archives are not supported for Huffman decompression.

**Note:** ZIP container overhead may increase file size for small files or already compressed data.
