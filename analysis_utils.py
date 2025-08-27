# analysis_utils.py
import pandas as pd

def compute_user_stats(df_responses: pd.DataFrame, df_questions: pd.DataFrame):
    df = df_responses.merge(df_questions[["id","topic"]], left_on="question_id", right_on="id", how="left")
    topic_acc = df.groupby("topic")["is_correct"].mean().fillna(0).reset_index().rename(columns={"is_correct":"accuracy"})
    overall = df["is_correct"].mean()
    return overall, topic_acc

def compute_class_comparison(df_all_responses: pd.DataFrame, df_questions: pd.DataFrame, user_id: int):
    df = df_all_responses.merge(df_questions[["id","topic"]], left_on="question_id", right_on="id", how="left")
    user_df = df[df.user_id == user_id]
    user_topic = user_df.groupby("topic")["is_correct"].mean().fillna(0)
    class_topic = df.groupby("topic")["is_correct"].mean().fillna(0)
    comp = pd.concat([user_topic.rename("user"), class_topic.rename("class")], axis=1).fillna(0).reset_index()
    return comp
