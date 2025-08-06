import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

logger = logging.getLogger(__name__)

class TradingModel:
    """
    Machine Learning model for trading predictions
    """
    
    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_columns = []
        self.model_path = 'models/trading_model.pkl'
        self.scaler_path = 'models/scaler.pkl'
        
        # Create models directory if it doesn't exist
        os.makedirs('models', exist_ok=True)
    
    def prepare_features(self, df):
        """Prepare features for ML model"""
        try:
            feature_df = df.copy()
            
            # Remove non-numeric columns and NaN values
            numeric_columns = feature_df.select_dtypes(include=[np.number]).columns.tolist()
            
            # Exclude target-related columns if they exist
            exclude_columns = ['open', 'high', 'low', 'volume', 'timestamp']
            feature_columns = [col for col in numeric_columns if col not in exclude_columns]
            
            if not feature_columns:
                logger.warning("No suitable feature columns found")
                return None, []
            
            # Fill NaN values with forward fill, then backward fill
            feature_df[feature_columns] = feature_df[feature_columns].ffill().bfill()
            
            # Drop rows that still have NaN values
            feature_df = feature_df[feature_columns].dropna()
            
            if feature_df.empty:
                logger.warning("No data available after cleaning")
                return None, []
            
            self.feature_columns = feature_columns
            logger.info(f"Prepared {len(feature_columns)} features: {feature_columns}")
            
            return feature_df, feature_columns
            
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None, []
    
    def create_target(self, df, lookahead=1):
        """Create target variable (1 if price goes up, 0 if down)"""
        try:
            df = df.copy()
            df['future_price'] = df['close'].shift(-lookahead)
            df['target'] = (df['future_price'] > df['close']).astype(int)
            
            # Remove rows where we can't predict
            df = df[:-lookahead]
            
            return df['target']
            
        except Exception as e:
            logger.error(f"Error creating target: {e}")
            return None
    
    def train(self, df):
        """Train the ML model"""
        try:
            logger.info("Starting model training...")
            
            # Prepare features
            feature_data, feature_cols = self.prepare_features(df)
            if feature_data is None:
                logger.error("Failed to prepare features for training")
                return False
            
            # Create target
            target = self.create_target(df)
            if target is None:
                logger.error("Failed to create target for training")
                return False
            
            # Align feature data with target
            min_length = min(len(feature_data), len(target))
            X = feature_data.iloc[:min_length]
            y = target.iloc[:min_length]
            
            if len(X) < 50:
                logger.warning(f"Not enough data for training: {len(X)} samples")
                return False
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            train_score = self.model.score(X_train_scaled, y_train)
            test_score = self.model.score(X_test_scaled, y_test)
            
            logger.info(f"Model trained successfully - Train score: {train_score:.4f}, Test score: {test_score:.4f}")
            
            # Save model
            self.save_model()
            
            self.is_trained = True
            return True
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False
    
    def predict(self, df):
        """Make prediction on new data"""
        try:
            # Try to load model if not trained
            if not self.is_trained:
                if not self.load_model():
                    logger.warning("Model not trained and cannot be loaded, using fallback")
                    return None
            
            # Prepare features
            feature_data, _ = self.prepare_features(df)
            if feature_data is None:
                return None
            
            # Use only the last row for prediction
            X = feature_data.iloc[[-1]]
            
            # Make sure we have the same features as training
            if self.feature_columns:
                missing_cols = [col for col in self.feature_columns if col not in X.columns]
                if missing_cols:
                    logger.warning(f"Missing feature columns: {missing_cols}")
                    return None
                
                X = X[self.feature_columns]
            
            # Scale features
            X_scaled = self.scaler.transform(X)
            
            # Make prediction
            prediction = self.model.predict(X_scaled)[0]
            probability = self.model.predict_proba(X_scaled)[0]
            
            return {
                'prediction': prediction,
                'probability': probability[1],  # Probability of price going up
                'features': X.iloc[0].to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return None
    
    def optimize_parameters(self, df):
        """Optimize model parameters"""
        try:
            logger.info("Starting parameter optimization...")
            
            # Prepare data
            feature_data, feature_cols = self.prepare_features(df)
            if feature_data is None:
                return None
            
            target = self.create_target(df)
            if target is None:
                return None
            
            min_length = min(len(feature_data), len(target))
            X = feature_data.iloc[:min_length]
            y = target.iloc[:min_length]
            
            if len(X) < 100:
                logger.warning("Not enough data for parameter optimization")
                return None
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Parameter grid
            param_grid = {
                'n_estimators': [50, 100, 200],
                'max_depth': [5, 10, 15],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4]
            }
            
            # Grid search
            grid_search = GridSearchCV(
                RandomForestClassifier(random_state=42),
                param_grid,
                cv=3,
                scoring='accuracy',
                n_jobs=-1
            )
            
            grid_search.fit(X_scaled, y)
            
            # Update model with best parameters
            self.model = grid_search.best_estimator_
            self.is_trained = True
            
            # Save optimized model
            self.save_model()
            
            logger.info(f"Parameter optimization complete. Best score: {grid_search.best_score_:.4f}")
            
            return {
                'best_score': grid_search.best_score_,
                'model_params': grid_search.best_params_,
                'top_features': feature_cols[:10]  # Top 10 features
            }
            
        except Exception as e:
            logger.error(f"Error optimizing parameters: {e}")
            return None
    
    def save_model(self):
        """Save trained model"""
        try:
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            logger.info("Model saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False
    
    def load_model(self):
        """Load trained model"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.is_trained = True
                logger.info("Model loaded successfully")
                return True
            else:
                logger.warning("Model files not found")
                return False
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False