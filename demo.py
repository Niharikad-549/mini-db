"""A short command-line tour of the persistent key-value database."""

from pathlib import Path

from database import Database


def main() -> None:
    demo_path = Path(__file__).with_name("demo.data")
    database = Database(demo_path)
    database.reset()
    database.put(12, "Ada")
    database.put(7, "Grace")
    database.put(24, "Edsger")
    print("Get key 12:", database.get(12)[0])
    print("Range 7 through 20:", database.range(7, 20))
    print("Delete key 7:", database.delete(7))
    print("Get deleted key 7:", database.get(7)[0])
    database.reset()


if __name__ == "__main__":
    main()