# gamification.py
import streamlit as st
from datetime import datetime, timedelta

# --- CONFIGURATION ---
XP_PER_TASK_SCHEDULED = 100
XP_PER_TODO_COMPLETED = 25
XP_PER_FOCUS_SESSION = 200
XP_FOR_LEVEL_UP = 500

STREAK_TIMEFRAME_HOURS = 36 # Allow 1.5 days between tasks to maintain a streak

# --- QUESTS ---
# {quest_id: (description, goal, reward_xp, progress_check_function)}
QUESTS = {
    "first_quest": ("Schedule your first 3 tasks", 3, 300, lambda s: s.tasks_completed),
    "pomodoro_pro": ("Complete 5 Focus Sessions", 5, 500, lambda s: s.get("focus_sessions_completed", 0)),
    "weekly_warrior": ("Maintain a 7-day streak", 7, 1000, lambda s: s.streak)
}

def initialize_gamification():
    """Initializes all gamification stats in session_state if they don't exist."""
    defaults = {
        "xp": 0, "level": 1, "tasks_completed": 0, "streak": 0,
        "last_task_timestamp": None, "completed_quests": [],
        "focus_sessions_completed": 0, "todos_completed": 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def award_xp(amount, event_type="task"):
    """Awards XP, handles leveling up, and updates streaks."""
    feedback = []
    st.session_state.xp += amount
    feedback.append(f"You earned {amount} XP!")

    # Level Up Logic
    while st.session_state.xp >= XP_FOR_LEVEL_UP:
        st.session_state.xp -= XP_FOR_LEVEL_UP
        st.session_state.level += 1
        feedback.append(f"🎉 **Level Up!** You've reached Level {st.session_state.level}! 🎉")
        st.balloons()
    
    # Smart Streak Logic
    if event_type in ["task", "todo", "focus"]: # Only these activities count for streaks
        now = datetime.now()
        if st.session_state.last_task_timestamp:
            last_time = datetime.fromisoformat(st.session_state.last_task_timestamp)
            if (now - last_time) > timedelta(hours=STREAK_TIMEFRAME_HOURS):
                st.session_state.streak = 1 # Reset streak
                feedback.append("It's been a while! You've started a new streak.")
            else:
                # To prevent multiple streak increments on the same day, we check the date
                if now.date() > last_time.date():
                    st.session_state.streak += 1
                    feedback.append(f"🔥 You're on a {st.session_state.streak}-day streak! Keep it up!")
        else:
            st.session_state.streak = 1 # First ever task
            feedback.append("You've started your first streak!")
        
        st.session_state.last_task_timestamp = now.isoformat()

    # Quest Completion Logic
    for quest_id, (desc, goal, reward, checker) in QUESTS.items():
        if quest_id not in st.session_state.completed_quests:
            if checker(st.session_state) >= goal:
                st.session_state.completed_quests.append(quest_id)
                st.session_state.xp += reward
                feedback.append(f"🏆 **Quest Complete:** {desc}! You earned a bonus {reward} XP!")

    return " ".join(feedback)

def display_gamification_dashboard():
    """Renders the gamification stats in the sidebar."""
    st.sidebar.header(f"🏆 {st.session_state.get('user_profile',{}).get('name','User')}'s Dashboard")
    
    st.sidebar.metric(label="Level", value=st.session_state.level)
    st.sidebar.progress(st.session_state.xp / XP_FOR_LEVEL_UP)
    st.sidebar.write(f"{st.session_state.xp} / {XP_FOR_LEVEL_UP} XP")
    
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Streak", f"{st.session_state.streak} 🔥")
    col2.metric("Tasks", st.session_state.tasks_completed)
    
    st.sidebar.subheader("Active Quests")
    active_quests_found = False
    for quest_id, (desc, goal, _, checker) in QUESTS.items():
        if quest_id not in st.session_state.completed_quests:
            progress = checker(st.session_state)
            st.sidebar.write(f"**{desc}** ({progress}/{goal})")
            st.sidebar.progress(progress / goal)
            active_quests_found = True
            
    if not active_quests_found:
        st.sidebar.info("You've completed all available quests! More coming soon.")