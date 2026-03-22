# Dev Troubleshooting

## Frontend changes not showing

1. **Hard refresh** – `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows) to bypass cache
2. **Restart dev server** – Stop (`Ctrl+C`) and run `yarn start` again (cached bundles can persist)
3. **Clear browser cache** – DevTools → Application → Clear storage
4. **Confirm dev mode** – You should see hot-reload messages in the terminal when editing `src/` files

## Slow initial load

- **AIChatbot** is lazy-loaded; it only loads when the chat panel is opened
- **External scripts** (emergent, PostHog) load with `defer` so they don’t block rendering
- First load may still be slow due to large bundles (Recharts, Radix UI, etc.)

