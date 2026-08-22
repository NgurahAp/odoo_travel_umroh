def is_travel_manager_or_admin(env):
    return env.is_admin() or env.user.has_group(
        "travel_umroh.group_travel_manager"
    )
