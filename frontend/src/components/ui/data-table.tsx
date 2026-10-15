import * as React from 'react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from './table';

export interface DataTableColumn<Row> {
  key: string;
  header: string;
  cell: (row: Row) => React.ReactNode;
  className?: string;
}

interface DataTableProps<Row> {
  columns: readonly DataTableColumn<Row>[];
  rows: readonly Row[];
  getRowKey: (row: Row) => React.Key;
  emptyMessage?: string;
}

export function DataTable<Row>({
  columns,
  rows,
  getRowKey,
  emptyMessage = 'Нет данных',
}: DataTableProps<Row>) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead className={column.className} key={column.key}>
                {column.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length > 0 ? (
            rows.map((row) => (
              <TableRow key={getRowKey(row)} className="transition-all duration-200 ease-in-out hover:bg-ink-900">
                {columns.map((column) => (
                  <TableCell className={column.className} key={column.key}>
                    {column.cell(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                className="py-10 text-center text-chrome-500"
                colSpan={columns.length}
              >
                {emptyMessage}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}