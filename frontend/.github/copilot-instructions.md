# Copilot Instructions for operator-360

This project is a React application bootstrapped with Create React App. Follow these guidelines to ensure AI agents are productive and maintain project conventions.

## Architecture Overview
- **Single-page React app**: Entry point is `src/index.js`, which renders the `App` component from `src/App.js`.
- **Component structure**: All UI logic resides in `src/`, with `App.js` as the main component. Styles are in `App.css` and `index.css`.
- **Performance reporting**: `reportWebVitals.js` integrates web-vitals for optional performance analytics.
- **Testing**: Tests are colocated with components, e.g., `App.test.js` for `App.js`. Jest and React Testing Library are used, configured via `setupTests.js`.

## Developer Workflows
- **Start development server**: `npm start` (runs on [http://localhost:3000](http://localhost:3000))
- **Run tests**: `npm test` (interactive watch mode)
- **Build for production**: `npm run build` (outputs to `build/`)
- **Eject config**: `npm run eject` (irreversible; copies config files for advanced customization)

## Project-Specific Conventions
- **No custom routing or state management**: Only React core and Create React App defaults are used.
- **Testing pattern**: Use React Testing Library for rendering and assertions. Example:
  ```js
  render(<App />);
  expect(screen.getByText(/learn react/i)).toBeInTheDocument();
  ```
- **Performance hooks**: To enable web-vitals logging, pass a function to `reportWebVitals` in `index.js`.
- **Styling**: Use CSS files in `src/` for component styles. No CSS-in-JS or preprocessors.

## External Dependencies
- **React 19.x**
- **React Scripts 5.x**
- **Testing Library**: `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`
- **web-vitals** for performance metrics

## Key Files & Patterns
- `src/App.js`, `src/App.test.js`: Main component and its test
- `src/index.js`: App entry point and performance hook
- `src/reportWebVitals.js`: Performance analytics integration
- `src/setupTests.js`: Jest DOM setup
- `public/index.html`: HTML template

## Example: Adding a New Component
1. Create `src/NewComponent.js` and `src/NewComponent.test.js`.
2. Import and use in `App.js`.
3. Style with a new or existing CSS file.

---
For more details, see [README.md](../README.md) and [Create React App docs](https://facebook.github.io/create-react-app/docs/getting-started).

> Please review and suggest improvements or clarify any missing project-specific patterns.