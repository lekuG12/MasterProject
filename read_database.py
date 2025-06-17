import sqlite3
import pandas as pd
from datetime import datetime

def read_nurse_talk_db():
    """Read and analyze the nurse_talk.db database"""
    try:
        # Connect to the database
        conn = sqlite3.connect('instance/nurse_talk.db')
        
        # Read conversations table into a pandas DataFrame
        query = """
        SELECT 
            phone_number,
            timestamp,
            user_input,
            bot_response,
            response_time,
            status
        FROM conversation
        ORDER BY timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn)
        
        # Basic analysis
        print("\n=== Nurse Talk Database Analysis ===\n")
        
        print(f"Total conversations: {len(df)}")
        print(f"Unique users: {df['phone_number'].nunique()}")
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        print("\nStatus distribution:")
        print(df['status'].value_counts())
        
        print("\nAverage response time: {:.2f} seconds".format(df['response_time'].mean()))
        
        print("\nMost common user inputs:")
        print(df['user_input'].value_counts().head())
        
        # Save to CSV for further analysis
        output_file = 'conversation_history.csv'
        df.to_csv(output_file, index=False)
        print(f"\nFull conversation history exported to {output_file}")
        
        return df
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    read_nurse_talk_db()