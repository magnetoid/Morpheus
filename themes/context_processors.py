"""Theme context processor — exposes active theme config to all templates."""


def theme_context(request):
    from themes.registry import theme_registry

    theme = theme_registry.active
    if not theme:
        return {}
    return {
        'active_theme': theme,
        'theme_config': theme.get_config(),
        'theme_name': theme.name,
    }
