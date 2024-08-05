import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# 示例数据
data = {
    'Q1': [1, 2, 3, 4, 5, 1],
    'Q2': [5, 4, 3, 2, 1, 4],
    'Q3': [2, 3, 4, 5, 1, 3],
    'Q4': [1, 0, 2, 4, 5, 1]
}
df = pd.DataFrame(data)

# 目标问卷（假设是第一套问卷）
target = df.iloc[0]

# 计算余弦相似度
cos_sim = cosine_similarity([target], df)[0]
df['cosine_similarity'] = cos_sim

# 计算皮尔逊相关系数
df['pearson_correlation'] = df.apply(lambda row: target.corr(row), axis=1)

# 结果比较
df_sorted_cos = df.sort_values(by='cosine_similarity', ascending=False)
df_sorted_pearson = df.sort_values(by='pearson_correlation', ascending=False)

# 显示结果
print("余弦相似度结果：")
print(df_sorted_cos)
print("\n皮尔逊相关系数结果：")
print(df_sorted_pearson)
