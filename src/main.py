import json
from pathlib import Path

from dotenv import load_dotenv

from .extract import load_file
from .llm_helper import get_transformation_rules, save_rules_to_file
from .profiler import build_dataset_profile
from .transform import apply_llm_rules


def main():
    load_dotenv()

    input_file = "data/in/raw_file.csv"
    rules_output = "reports/execution/llm_rules.json"
    cleaned_output = "data/processed/cleaned_file.csv"
    steps_output = "reports/execution/applied_steps.json"

    Path(rules_output).parent.mkdir(parents=True, exist_ok=True)
    Path(cleaned_output).parent.mkdir(parents=True, exist_ok=True)
    Path(steps_output).parent.mkdir(parents=True, exist_ok=True)

    # 1. Extraction
    df = load_file(input_file)

    # 2. Profiling
    profile = build_dataset_profile(df)

    # 3. Regles LLM
    llm_rules = get_transformation_rules(profile, dataframe=df)
    save_rules_to_file(llm_rules, rules_output)

    # 4. Application des regles
    cleaned_df, applied_steps = apply_llm_rules(df, llm_rules)

    # 5. Sauvegarde du fichier nettoye
    cleaned_df.to_csv(cleaned_output, index=False, encoding="utf-8")

    # 6. Sauvegarde des etapes appliquees
    with open(steps_output, "w", encoding="utf-8") as f:
        json.dump(applied_steps, f, indent=2, ensure_ascii=False)

    print("Pipeline ETL + LLM termine avec succes.")
    print("Etapes appliquees :")
    for step in applied_steps:
        print("-", step)


if __name__ == "__main__":
    main()
