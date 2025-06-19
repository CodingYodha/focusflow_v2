# gamification.py
import streamlit as st

# Define badge criteria: {badge_name: (description, icon, condition_function)}
BADGE_CRITERIA = {
    "First Task": ("Complete your first task", "🥇", lambda s: s.tasks_completed == 1),
    "Task Master": ("Complete 5 tasks", "🏆", lambda s: s.tasks_completed == 5),
    "Scheduling Pro": ("Complete 10 tasks", "🚀", lambda s: s.tasks_completed == 10),
    "3-Day Streak": ("Maintain a 3-day streak", "🔥", lambda s: s.streak >= 3),
}

XP_PER_TASK = 100
XP_FOR_LEVEL_UP = 500

def add_xp(xp_to_add):
    """Adds XP and handles leveling up."""
    st.session_state.xp += xp_to_add
    leveled_up = False
    while st.session_state.xp >= XP_FOR_LEVEL_UP:
        st.session_state.xp -= XP_FOR_LEVEL_UP
        st.session_state.level += 1
        leveled_up = True
    return leveled_up

def update_gamification_stats():
    """Call this after a task is successfully added."""
    st.session_state.tasks_completed += 1
    
    # Simple streak logic (can be improved with timestamps)
    # For a hackathon, this simple increment is fine.
    st.session_state.streak += 1 

    leveled_up = add_xp(XP_PER_TASK)
    new_badges = check_for_new_badges()

    feedback = f"Task added! You earned {XP_PER_TASK} XP. "
    if leveled_up:
        feedback += f"Congratulations, you reached Level {st.session_state.level}! "
        st.balloons()
    if new_badges:
        feedback += f"You've unlocked new badge(s): {', '.join(new_badges)}!"
    
    return feedback

def check_for_new_badges():
    """Checks if the user has met the criteria for any new badges."""
    newly_earned = []
    for badge, (desc, icon, condition) in BADGE_CRITERIA.items():
        if badge not in st.session_state.badges and condition(st.session_state):
            st.session_state.badges.append(badge)
            newly_earned.append(f"{icon} {badge}")
    return newly_earned

def display_gamification_dashboard():
    """Renders the gamification stats in the sidebar."""
    st.sidebar.header("🏆 Your Progress")
    
    # Level and XP
    st.sidebar.metric(label="Level", value=st.session_state.level)
    st.sidebar.write("XP Progress:")
    st.sidebar.progress(st.session_state.xp / XP_FOR_LEVEL_UP)
    st.sidebar.write(f"{st.session_state.xp} / {XP_FOR_LEVEL_UP} XP")
    
    # Other Stats
    st.sidebar.metric(label="Tasks Completed", value=st.session_state.tasks_completed)
    st.sidebar.metric(label="Current Streak", value=f"{st.session_state.streak} days 🔥")
    
    # Badges
    st.sidebar.subheader("Badges Unlocked")
    if not st.session_state.badges:
        st.sidebar.write("No badges yet. Keep going!")
    else:
        for badge_name in st.session_state.badges:
            desc, icon, _ = BADGE_CRITERIA[badge_name]
            st.sidebar.markdown(f"**{icon} {badge_name}**: {desc}")