# Montenegro Experience brand assets

User-supplied approved logo. Original is retained; WebP only trims outer white margin (1146x317), preserves white background and aspect ratio.

This Montenegro-only theme uses /media/store/montenegro-experience-logo.webp in header and footer. StoreSettings.logo on the Montenegro deployment points at that same persistent media asset, covering consumers of the existing branding settings (including publisher metadata). Provision this file into the instance media storage when creating a fresh deployment; do not set other stores to this logo. Other theme files are unchanged.

Live update applied to Montenegro only; this source branch must be incorporated into the next deployed source before rebuilding that instance, otherwise the template change will revert. The media file and StoreSettings value persist independently. No main-branch merge or cross-store deployment is implied.
