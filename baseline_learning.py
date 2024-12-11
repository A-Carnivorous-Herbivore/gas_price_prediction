# -*- coding: utf-8 -*-
"""Baseline Learning.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1g5oSPFGWIXi9jPtob9qg11KJMpwMn7Bh

# Initial Setup
"""

# !pip install netcdf4 pydap

import gdown
import itertools
import numpy as np
import pandas as pd
import xarray as xr
import xarray as xr
import datetime as dt
import plotly.express as px
from scipy.stats import zscore
from sklearn.preprocessing import StandardScaler
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

exports_url = "https://drive.google.com/file/d/1J27j-yAZhe9tiQiJbctpL44QJ97nA4sV/view?usp=drive_link"
imports_url = "https://drive.google.com/file/d/1HS8YdIXwkHTxnq0CzJzJX1wUi_dvtznM/view?usp=drive_link"
net_imports_url = "https://drive.google.com/file/d/1ibxyKMBfs1WFNuYyUkmxf9k9jC_zuniX/view?usp=drive_link"
gas_prices_url = "https://drive.google.com/file/d/1rODElv0oLcJGLZufTfoLFhastfiMaLfX/view?usp=sharing"
tavg_url = "https://drive.google.com/file/d/1l6RLFWmVHtsQP4nGPKta9zvJAiJR71DS/view?usp=sharing"

exports = pd.read_csv('https://drive.google.com/uc?export=download&id=' + exports_url.split('/')[-2], skiprows=2)
imports = pd.read_csv('https://drive.google.com/uc?export=download&id=' + imports_url.split('/')[-2], skiprows=2)
net_imports = pd.read_csv('https://drive.google.com/uc?export=download&id=' + net_imports_url.split('/')[-2], skiprows=2)
gas_prices = pd.read_csv('https://drive.google.com/uc?export=download&id=' + gas_prices_url.split('/')[-2], skiprows=2)

"""Notes:
- **Exports**: Data (except for exports of crude oil and petroleum) is available after June 04, 2010. It is available for ethanol after May 26, 2023.
- **Imports**: Data for imports of crude oil, petroleum available after Jan 5, 1990. Summation of these only available after Feb 8, 1991.
- **Net imports**: This is simply imports - exports, but some of the data is unavailable (even when the data is available for both imports and exports). Thus, it is best to construct these features ourselves.
-  **Gas Prices**: Available April 5, 1993 - Oct 11, 2024. Will probably need to merge the rest of the data based on these dates.


General Notes:
- All dates are weekly
"""

exports = exports.drop(columns=['Unnamed: 11'])
exports['Date'] = pd.to_datetime(exports['Date'])
imports = imports.drop(columns=['Unnamed: 36'])
imports['Date'] = pd.to_datetime(imports['Date'])
gas_prices['Date'] = pd.to_datetime(gas_prices['Date'])

# Last value of each df is always NaN
exports = exports[:-1]
imports = imports[:-1]
gas_prices = gas_prices[:-1]

export_columns = {}
for column in exports.columns:
  export_columns[column] = ' '.join(column.replace('Weekly U.S.', '').replace('Exports of', '').replace('(Thousand Barrels per Day)', '(Exports)').split())

import_columns = {}
for column in imports.columns:
  import_columns[column] = ' '.join(column.replace('Weekly U.S.', '').replace('Imports of', '').replace('(Thousand Barrels per Day)', '(Imports)').split())

exports = exports.rename(columns = export_columns)
imports = imports.rename(columns = import_columns)
gas_prices = gas_prices.rename(columns = {'Weekly U.S. All Grades All Formulations Retail Gasoline Prices  (Dollars per Gallon)': 'Gas Prices'})

"""Note: For now, we can use `merged_df_simple`, which only has date, gas price, and imports/exports of crude oil and petroleum. In the future, we may look at more advanced features, which are contained in `merged_df_all_features`.

Merge data and find net imports (imports - exports)
"""

# Merge
merged_df_all_features = pd.merge_asof(gas_prices, imports, on='Date', direction='backward')
merged_df_all_features = pd.merge_asof(merged_df_all_features, exports, on='Date', direction='backward')

# Find Net Imports (Similar to net_imports df but with all dates)
reduced_columns = ['Crude Oil', 'Total Petroleum Products', 'Crude Oil and Petroleum Products']
for col in reduced_columns:
  merged_df_all_features[col + ' (Net Imports)'] = merged_df_all_features[col + ' (Imports)'] - merged_df_all_features[col + ' (Exports)']

cols = ['Date', 'Gas Prices'] + [col + ' (Imports)' for col in reduced_columns] + [col + ' (Exports)' for col in reduced_columns] + [col + ' (Net Imports)' for col in reduced_columns]

merged_df_simple = merged_df_all_features[cols]

"""Training, validation, testing (for use later)"""

# Get training, validation, testing sets
train_size = 0.7
validation_size = 0.15
n = len(merged_df_simple)

training_simple = merged_df_simple[:int(train_size * n)]
validation_simple = merged_df_simple[int(train_size * n):int((train_size + validation_size) * n)]
test_simple = merged_df_simple[int((train_size + validation_size) * n):]

test_simple.head()

"""# Baseline Modelling

It is essential to develop a baseline model before implementing complex solution to roughly estimate the sanity result; in this project, we will be using linear regression as the baseline model to predict gas price.

**Note: We will be using data in the last time interval for prediction.**

To effectively predict gas prices at interval n, the model should leverage the gas price at interval n - 1 along with the import/export data at interval n. This approach ensures that the prediction at each step ONLY considers the previous state of the gas price while incorporating the most recent import/export data, following a Markov Chain process. As such, the prediction at any given interval only depends on the prior state and the current inputs, which can be thought of as a simplified model of RNN.
"""

merged_df_simple = merged_df_simple.copy()
merged_df_simple['previous_price'] = merged_df_simple['Gas Prices'].shift(1)
merged_df_simple = merged_df_simple.dropna()

training_simple = training_simple.copy()
training_simple['previous_price'] = training_simple['Gas Prices'].shift(1)
training_simple = training_simple.dropna()

validation_simple = validation_simple.copy()
validation_simple['previous_price'] = validation_simple['Gas Prices'].shift(1)
validation_simple = validation_simple.dropna()

test_simple = test_simple.copy()
test_simple['previous_price'] = test_simple['Gas Prices'].shift(1)
test_simple = test_simple.dropna()

validation_simple.head()
# validation_simple.shape

"""**Note: We will need to magnify the price labels; othersie, the mean square error calculation will be very small.**"""

merged_df_simple.loc[:, 'Gas Prices'] = merged_df_simple['Gas Prices'] * 100
merged_df_simple.loc[:, 'previous_price'] = merged_df_simple['previous_price'] * 100
training_simple.loc[:, 'Gas Prices'] = training_simple['Gas Prices'] * 100
training_simple.loc[:, 'previous_price'] = training_simple['previous_price'] * 100
validation_simple.loc[:, 'Gas Prices'] = validation_simple['Gas Prices'] * 100
validation_simple.loc[:, 'previous_price'] = validation_simple['previous_price'] * 100
test_simple.loc[:, 'Gas Prices'] = test_simple['Gas Prices'] * 100
test_simple.loc[:, 'previous_price'] = test_simple['previous_price'] * 100

validation_simple.head()

"""
Now, we would like to see which combination of features can provide the best result to decide the importance of features. We will use all combination of 12 features and record the best one with lowest MSE loss with validation dataset after being trained on training dataset.
"""

feature_columns = ['Crude Oil (Imports)', 'Total Petroleum Products (Imports)',
                   'Crude Oil and Petroleum Products (Imports)', 'Crude Oil (Exports)',
                   'Total Petroleum Products (Exports)', 'Crude Oil and Petroleum Products (Exports)',
                   'Crude Oil (Net Imports)', 'Total Petroleum Products (Net Imports)',
                   'Crude Oil and Petroleum Products (Net Imports)', 'previous_price']

features = training_simple[feature_columns]
predicted_price = training_simple['Gas Prices']


best_mse = float(1e10)
best_combination = None

# Use all possible combinations of features
combination_nums = 0
for i in range(1, len(feature_columns) + 1):
    for combination in itertools.combinations(feature_columns, i):
        combination_nums += 1
        features = training_simple[list(combination)]
        price_label = training_simple['Gas Prices']

        model = LinearRegression()
        model.fit(features, price_label)

        feature_validation = validation_simple[list(combination)]
        price_validation = validation_simple['Gas Prices']
        validation_price_pred = model.predict(feature_validation)

        # Calculate the current MSE
        mse = mean_squared_error(price_validation, validation_price_pred)
        # print(f"Combination: {combination}, MSE: {mse:.2f}")

        # Record the best value
        if mse < best_mse:
            best_mse = mse
            best_combination = combination

print(f"Among {combination_nums} ways of feature combinations, \nBest Combination: {best_combination}, Best MSE: {best_mse}")

"""
We can see that, by training linear regression models with all possible combinations of features provided in the dataset, the best combination evaluated with validation dataset is using ['Crude Oil (Imports)', 'Total Petroleum Products (Net Imports)', 'previous_price'] as input features, which gives a best MSE error of 18.12 after being scaled 10000 times (because scaling price by 100 means the square of error is scaled 100 * 100 = 10000).

Now, we will normalize the input data and see if there is any affect on the result."""

# Reset all the data
merged_df_all_features = pd.merge_asof(gas_prices, imports, on='Date', direction='backward')
merged_df_all_features = pd.merge_asof(merged_df_all_features, exports, on='Date', direction='backward')

reduced_columns = ['Crude Oil', 'Total Petroleum Products', 'Crude Oil and Petroleum Products']
for col in reduced_columns:
  merged_df_all_features[col + ' (Net Imports)'] = merged_df_all_features[col + ' (Imports)'] - merged_df_all_features[col + ' (Exports)']

cols = ['Date', 'Gas Prices'] + [col + ' (Imports)' for col in reduced_columns] + [col + ' (Exports)' for col in reduced_columns] + [col + ' (Net Imports)' for col in reduced_columns]

merged_df_simple = merged_df_all_features[cols]

train_size = 0.7
validation_size = 0.15
n = len(merged_df_simple)

training_simple = merged_df_simple[:int(train_size * n)]
validation_simple = merged_df_simple[int(train_size * n):int((train_size + validation_size) * n)]
test_simple = merged_df_simple[int((train_size + validation_size) * n):]

merged_df_simple = merged_df_simple.copy()
merged_df_simple['previous_price'] = merged_df_simple['Gas Prices'].shift(1)
merged_df_simple = merged_df_simple.dropna()

training_simple = training_simple.copy()
training_simple['previous_price'] = training_simple['Gas Prices'].shift(1)
training_simple = training_simple.dropna()

validation_simple = validation_simple.copy()
validation_simple['previous_price'] = validation_simple['Gas Prices'].shift(1)
validation_simple = validation_simple.dropna()

test_simple = test_simple.copy()
test_simple['previous_price'] = test_simple['Gas Prices'].shift(1)
test_simple = test_simple.dropna()

"""Now, let us see if taking normalization would bring in better results on feature selections and linear regression."""

feature_columns = ['Crude Oil (Imports)', 'Total Petroleum Products (Imports)',
                   'Crude Oil and Petroleum Products (Imports)', 'Crude Oil (Exports)',
                   'Total Petroleum Products (Exports)', 'Crude Oil and Petroleum Products (Exports)',
                   'Crude Oil (Net Imports)', 'Total Petroleum Products (Net Imports)',
                   'Crude Oil and Petroleum Products (Net Imports)', 'previous_price']

feature_train = training_simple[feature_columns]
y_train = training_simple['Gas Prices']

feature_val = validation_simple[feature_columns]
y_val = validation_simple['Gas Prices']


feature_scaler = StandardScaler()
target_scaler = StandardScaler()


feature_train_scaled = feature_scaler.fit_transform(feature_train)
y_train_scaled = target_scaler.fit_transform(y_train.values.reshape(-1, 1)).ravel()


feature_val_scaled = feature_scaler.transform(feature_val)    # Only z-score the input of validation; the prediction should not be z-scored

best_mse = float('inf')
best_combination = None
combination_nums = 0

for i in range(1, len(feature_columns) + 1):
    for combination in itertools.combinations(range(len(feature_columns)), i):
        combination_nums += 1
        idx_list = list(combination)
        selected_features = [feature_columns[j] for j in idx_list]

        X_train_comb = feature_train_scaled[:, idx_list]
        X_val_comb = feature_val_scaled[:, idx_list]

        model = LinearRegression()
        model.fit(X_train_comb, y_train_scaled)

        val_pred = model.predict(X_val_comb)
        val_pred = target_scaler.inverse_transform(val_pred.reshape(-1, 1)).ravel()
        mse = mean_squared_error(y_val, val_pred)

        if mse < best_mse:
            best_mse = mse
            best_combination = selected_features

print(f"Among {combination_nums} ways of feature combinations,\nBest Combination: {best_combination}, Best MSE: {10000 * best_mse:.6f}")

"""# **Baseline Model Conclusion**

With comparison to results obtained without z-score normalization, we can conclude that ['Crude Oil (Imports)', 'Total Petroleum Products (Net Imports)', 'previous_price'] is the most important feature and the other input features are not very important respectively; with or without z-score normalization, we can reach the same conclusion of useful input features, from which we can conclude the input dataset covers most variety of data without bias. Therefore, our baseline model is presented; in addition, we have established a sense of feature importance, which will be helpful during development of RNN in our next stage of project.
"""