"""Packer simplifies and combines a set of python source files."""
import astroid
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--file", required=True)

def readfile(filename: str, encoding="utf-8")->str:
    with open(filename, "rt", encoding=encoding) as fileobj:
        return fileobj.read()

def pack_file(filename: str):
    """Pack file is the entry point for packing files.

    You call it first.
    """
    data = readfile(filename)
    tree = astroid.parse(data)
    nodes = [x for x in tree.body if hasattr(x,'body')]
    return nodes


def main():
    """Program entry point."""
    args = parser.parse_args()
    # astroid.MANAGER.register_transform(None
    print(pack_file(args.file))



if __name__ == "__main__":
    main()