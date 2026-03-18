---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces with intentional aesthetics, high craft, and non-generic visual identity.
---

# Frontend Design & Aesthetics

Use this skill whenever you are tasked with building or styling web user interfaces, components, or entire pages. This skill enforces high-end design standards that move beyond generic AI-generated aesthetics.

## Core Design Principles

### 1. Bold Typography
- **Header Fonts**: Use expressive, high-impact fonts for headers (e.g., 'Syne', 'Outfit', or 'Cabinet Grotesk').
- **Body Fonts**: Pair with clean, highly readable geometric sans-serifs (e.g., 'DM Sans', 'Inter').
- **Scale**: Use a bold typographic scale with significant contrast between headers and body.

### 2. Sophisticated Color Systems
- **Non-Generic Palettes**: Avoid basic CSS colors. Use curated HSL-tailored palettes.
- **Mesh Gradients**: Implement multi-layered radial gradients to create "mesh" background effects.
  ```css
  background: 
    radial-gradient(at 27% 37%, hsla(215, 98%, 61%, 0.3) 0px, transparent 50%),
    radial-gradient(at 97% 21%, hsla(125, 98%, 72%, 0.2) 0px, transparent 50%);
  ```
- **Glassmorphism**: Use `backdrop-filter: blur(12px)` with semi-transparent surfaces for a modern, sleek look.

### 3. Motion & Micro-interactions
- **Staggered Entrance**: Animate elements into view using staggered delays.
- **Cubic Bezier**: Use custom easing functions (e.g., `cubic-bezier(0.4, 0, 0.2, 1)`) for smooth, natural transitions.
- **Hover States**: Add meaningful transformations on hover (e.g., subtle scale-up, shadow depth increase, or reveal effects).
- **Floating Effects**: Use `@keyframes` to create continuous, subtle floating animations for background elements.

### 4. Visual Hierarchy & Space
- **Intentional Negative Space**: Use generous padding and margins to let the design "breathe".
- **Depth**: Create depth using layered shadows and perspective transforms.
- **Borders**: Prefer subtle gradients or low-opacity lines for borders instead of high-contrast solid lines.

## Implementation Checklist
- [ ] Are the headings using a distinctive font?
- [ ] Is there a sophisticated color palette (no generic primary colors)?
- [ ] Are there subtle micro-animations (hover transitions, entrance fades)?
- [ ] Does the layout feel balanced and spacious?
- [ ] Are you using modern CSS features like `grid`, `flex`, and `backdrop-filter`?

## Reference Code Patterns
### Floating Animation
```css
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}
```

### Premium Shadow
```css
box-shadow: 0 20px 50px -12px rgba(0, 0, 0, 0.25);
```
