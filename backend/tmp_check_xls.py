from pathlib import Path
import xlrd
p=Path('backend/uploads/dirty_logistics_50k.xls')
if not p.exists():
    print('MISSING')
else:
    try:
        bk=xlrd.open_workbook(str(p), ignore_workbook_corruption=True)
        print('SHEETS', bk.nsheets)
        s=bk.sheet_by_index(0)
        print('ROWS,COLS', s.nrows, s.ncols)
    except Exception as e:
        print('ERR', type(e), e)
