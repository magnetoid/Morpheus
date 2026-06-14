"""Product Stories — editable scroll-snap storytelling blocks on the PDP."""

from __future__ import annotations

from morpheus import DashboardPage, Plugin, StorefrontBlock


class ProductStoriesPlugin(Plugin):
    name = 'product_stories'
    label = 'Product Stories'
    version = '1.0.0'
    description = (
        'Scroll-snap "why you\'ll love it" story blocks on the product page — '
        'image + heading + body, ordered per product, editable in the dashboard.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.product_stories.urls_dashboard',
            prefix='dashboard/stories/',
            namespace='product_stories',
        )

    def contribute_storefront_blocks(self) -> list:
        # Renders on the real, theme-honoured slot (above the long description).
        return [
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='product_stories/blocks/story_rail.html',
                priority=30,
                context_keys=['product'],
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Product stories',
                slug='stories',
                view='plugins.installed.product_stories.dashboard.stories_index',
                icon='book-open',
                section='catalog',
                order=55,
                url='/dashboard/stories/',
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.product_stories.agent_tools import (
            stories_add_block_tool,
            stories_list_blocks_tool,
        )

        return [stories_list_blocks_tool, stories_add_block_tool]
