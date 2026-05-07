import sys

sys.path.insert(0, "src")
import pandas as pd

import rules_engine

df = pd.DataFrame(
    {
        "date_naissance": ["2019-09-15 00:00:00", "1980-05-05", "43700"],
        "prenom": ["John", "Jane", "Jules"],
        "nom": ["Doe", "Smith", "Briot"],
    }
)
out = rules_engine.derive_useful_columns(df, {})
print(out[["date_naissance", "age", "full_name"]].to_dict())
