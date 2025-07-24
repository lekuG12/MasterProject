# Algorithms Used in This Project

This document summarizes the main algorithms implemented in the project, their time and space complexity, and a brief explanation of their purpose and logic.

---

## 1. Symptom Deduplication (Diagnosis Section)

**Location:** `src/Backend/FlaskAPI/flasky.py` (`clean_response` function)

**Algorithm:**  
Iterates through diagnosis lines, normalizes each line, and adds it to the output only if it hasn't been seen before.

**Pseudocode:**
```
for diag in diagnosis_lines:
    norm_diag = diag.lower().strip('.')
    if norm_diag not in seen_diag and len(diag) > 3:
        deduped_diag.append(diag)
        seen_diag.add(norm_diag)
```

**Complexity:**  
- Time: O(n) where n is the number of diagnosis lines  
- Space: O(n) for storing seen lines

**Explanation:**  
This is a standard deduplication algorithm using a set for O(1) lookups. It ensures the diagnosis section does not repeat similar lines.

---

## 2. First Aid Step Deduplication and Emergency Filtering

**Location:** `src/Backend/FlaskAPI/flasky.py` (`clean_response` function)

**Algorithm:**  
Iterates through first aid steps, removes gibberish, deduplicates, and ensures only one emergency instruction is included.

**Pseudocode:**
```
for step in first_aid_lines:
    if gibberish_pattern in step:
        continue
    norm_step = step.lower().strip('.')
    if emergency_keywords in norm_step:
        if not emergency_added:
            unique_steps.append("Seek emergency medical care immediately.")
            emergency_added = True
        continue
    if norm_step not in seen_steps and len(step) > 3:
        unique_steps.append(step)
        seen_steps.add(norm_step)
```

**Complexity:**  
- Time: O(m) where m is the number of first aid lines  
- Space: O(m) for storing seen steps

**Explanation:**  
This algorithm filters out repeated and irrelevant first aid steps, and ensures only one emergency message is sent, improving clarity and reducing redundancy.

---

## 3. Conversation State Management

**Location:** `src/Backend/Model/conversation_state.py` (not shown, inferred from usage)

**Algorithm:**  
Each user (phone number) is mapped to a session object that tracks the state and symptom history.

**Complexity:**  
- Time: O(1) for state transitions and symptom additions  
- Space: O(u) where u is the number of concurrent users

**Explanation:**  
A dictionary or similar mapping is used to quickly retrieve and update the state for each user, enabling session continuity during a conversation.

---

## 4. Audio File Cleanup

**Location:** `src/Backend/FlaskAPI/flasky.py` (`cleanup_old_audio_files` function)

**Algorithm:**  
Iterates through files in the audio directory and deletes those older than 1 hour.

**Pseudocode:**
```
for filename in audio_dir:
    if file_creation_time < (current_time - 3600):
        remove(file_path)
```

**Complexity:**  
- Time: O(f) where f is the number of files in the audio directory  
- Space: O(1)

**Explanation:**  
A simple linear scan and conditional deletion to manage disk space.

---

## 5. Conversation History Retrieval

**Location:** `src/Backend/database/data.py` (`get_conversation_history` function)

**Algorithm:**  
Queries the SQLite database for all conversation records associated with a phone number.

**Complexity:**  
- Time: O(k) where k is the number of records for the user (depends on DB indexing)  
- Space: O(k)

**Explanation:**  
Standard database query to fetch and return all relevant conversation logs for a user.

---

## 6. Audio Transcription and TTS

**Location:** `src/AIV/translateTranscribe.py` (not shown, inferred)

**Algorithm:**  
- Audio files are transcribed using speech recognition libraries (likely O(n) where n is audio length).
- Text-to-speech is generated using gTTS or similar (O(n) where n is text length).

**Complexity:**  
- Time: O(n) for both transcription and TTS  
- Space: O(n)

**Explanation:**  
These are standard library calls for audio processing.

---

# Summary Table

| Algorithm                        | Time Complexity | Space Complexity | Purpose                                  |
|-----------------------------------|----------------|------------------|------------------------------------------|
| Symptom Deduplication             | O(n)           | O(n)             | Remove repeated diagnosis lines          |
| First Aid Deduplication/Filtering | O(m)           | O(m)             | Clean and filter first aid steps         |
| Conversation State Management     | O(1)           | O(u)             | Track user session state                 |
| Audio File Cleanup                | O(f)           | O(1)             | Remove old audio files                   |
| Conversation History Retrieval    | O(k)           | O(k)             | Fetch user conversation logs             |
| Audio Transcription/TTS           | O(n)           | O(n)             | Convert audio to text and vice versa     |

---

For more details, see the relevant source files in the `src/Backend/FlaskAPI/`, `src/Backend/database/`, and