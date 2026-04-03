from app.core.xgboost_model import get_scorer


def main() -> None:
    summary = get_scorer().retrain()
    print(summary)


if __name__ == "__main__":
    main()
