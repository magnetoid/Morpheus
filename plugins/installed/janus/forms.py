"""The Janus settings form."""

from __future__ import annotations

from urllib.parse import urlparse

from django import forms

from core.assistant import janus_settings

_PROVIDER_LABELS = {
    'openai': 'OpenAI',
    'anthropic': 'Anthropic',
    'gemini': 'Google Gemini',
    'deepseek': 'DeepSeek',
    'grok': 'xAI Grok',
}


def _provider_choices() -> list[tuple[str, str]]:
    from core.assistant.janus_engine import pinnable_providers

    return [('', 'Choose a provider')] + [
        (name, _PROVIDER_LABELS.get(name, name)) for name in pinnable_providers()
    ]


class JanusSettingsForm(forms.Form):
    enabled = forms.BooleanField(required=False)
    model_source = forms.ChoiceField(
        choices=[('store', "Use the store's AI provider"), ('custom', 'Pin a provider for Janus')]
    )
    provider = forms.ChoiceField(required=False)
    model = forms.CharField(required=False, max_length=100)
    base_url = forms.CharField(required=False, max_length=300)
    # Write-only: never rendered back, and blank keeps the stored key.
    api_key = forms.CharField(
        required=False, max_length=500, widget=forms.PasswordInput(render_value=False)
    )
    clear_api_key = forms.BooleanField(required=False)
    max_tool_turns = forms.IntegerField(min_value=1, max_value=janus_settings.MAX_TOOL_TURNS)
    turn_timeout_s = forms.IntegerField(
        min_value=janus_settings.MIN_TURN_TIMEOUT_S, max_value=janus_settings.MAX_TURN_TIMEOUT_S
    )
    extra_instructions = forms.CharField(
        required=False,
        max_length=janus_settings.MAX_EXTRA_INSTRUCTIONS,
        widget=forms.Textarea(attrs={'rows': 6}),
    )
    bundled_skills = forms.BooleanField(required=False)
    learning = forms.BooleanField(required=False)

    def __init__(self, *args, has_stored_key: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_stored_key = has_stored_key
        self.fields['provider'].choices = _provider_choices()

    def clean_model(self) -> str:
        model = (self.cleaned_data.get('model') or '').strip()
        if any(ch.isspace() for ch in model):
            raise forms.ValidationError('A model name has no spaces.')
        return model

    def clean_base_url(self) -> str:
        url = (self.cleaned_data.get('base_url') or '').strip()
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                raise forms.ValidationError('Use a full http:// or https:// address.')
        return url

    def clean(self) -> dict:
        data = super().clean()
        if data.get('model_source') == 'custom':
            if not data.get('provider'):
                self.add_error('provider', 'Choose the provider Janus should use.')
            if not data.get('model'):
                self.add_error('model', 'Enter the model Janus should use.')
            keeps_key = self.has_stored_key and not data.get('clear_api_key')
            if not data.get('api_key') and not keeps_key:
                self.add_error('api_key', 'Enter an API key for this provider.')
        return data
