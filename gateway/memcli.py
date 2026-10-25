"""Manual local memory operations; namespace is always explicit or controlled by env."""
import argparse
import json
import os
import sys
from memdb import connect, remember, forget, search, ingest_directory, entries_count, validate_namespace


def main(argv=None):
    parser = argparse.ArgumentParser(description='Private AI Pipeline v0.2: lokaler Wissensspeicher')
    parser.add_argument('--db', default=None)
    parser.add_argument('--namespace', default=os.getenv('MEMORY_NAMESPACE', 'personal'))
    sub = parser.add_subparsers(dest='action', required=True)
    add = sub.add_parser('remember'); add.add_argument('name'); add.add_argument('text')
    find = sub.add_parser('search'); find.add_argument('query')
    rem = sub.add_parser('forget'); rem.add_argument('name')
    imp = sub.add_parser('ingest'); imp.add_argument('folder', nargs='?', default='/documents')
    sub.add_parser('stats')
    sub.add_parser('export')
    args = parser.parse_args(argv)
    namespace = validate_namespace(args.namespace)
    with connect(args.db) as db:
        if args.action == 'remember':
            if ':' in args.name or not 0 < len(args.name) <= 250:
                parser.error('Ungültiger Notizname')
            remember(db, 'note:' + args.name, args.text, namespace)
            print('Notiz gespeichert:', args.name, 'Namespace:', namespace)
        elif args.action == 'search':
            print(json.dumps(search(db, args.query, 8, namespace), indent=2, ensure_ascii=False))
        elif args.action == 'forget':
            key = args.name if args.name.startswith(('note:', 'doc:')) else 'note:' + args.name
            print('Gelöschte Einträge:', forget(db, key, namespace))
        elif args.action == 'ingest':
            print(json.dumps(ingest_directory(db, args.folder, namespace=namespace), ensure_ascii=False))
        elif args.action == 'stats':
            print(json.dumps({'namespace': namespace, 'entries': entries_count(db, namespace)}))
        elif args.action == 'export':
            json.dump([{'namespace': namespace, 'source': s, 'body': b} for s, b in db.execute(
                'SELECT source, body FROM entries_v2 WHERE namespace=? ORDER BY source', (namespace,))],
                sys.stdout, ensure_ascii=False, indent=2)
            print()


if __name__ == '__main__':
    main()
