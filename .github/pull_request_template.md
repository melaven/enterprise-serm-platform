## Description
<!-- Опишите суть изменений -->

## Type of Change
<!-- Отметьте нужное: [x] -->

- [ ] 🐛 Bug fix (исправление бага)
- [ ] ✨ New feature (новая функциональность)
- [ ] 💥 Breaking change (изменения, ломающие обратную совместимость)
- [ ] 📝 Documentation (только документация)
- [ ] 🎨 Style (форматирование, стили)
- [ ] ♻️ Refactoring (рефакторинг без изменения функциональности)
- [ ] ⚡ Performance (оптимизация производительности)
- [ ] ✅ Tests (добавление или исправление тестов)
- [ ] 🔧 CI/CD (изменения в CI/CD)

## Related Issues
<!-- Ссылки на связанные issues -->

Closes #
Related to #

## Changes Made
<!-- Детальный список изменений -->

- 
- 
- 

## Screenshots (if applicable)
<!-- Скриншоты для UI изменений -->

<details>
<summary>Before / After</summary>

### Before
<!-- скриншот до изменений -->

### After
<!-- скриншот после изменений -->

</details>

## Testing
<!-- Как были протестированы изменения -->

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed
- [ ] Tested on multiple browsers (Chrome, Firefox, Safari)
- [ ] Tested on mobile devices
- [ ] Tested with Demo Mode enabled
- [ ] Tested with backend API

## Checklist
<!-- Убедитесь, что все пункты выполнены -->

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code in hard-to-understand areas
- [ ] I have updated the documentation accordingly
- [ ] My changes generate no new warnings or errors
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing unit tests pass locally
- [ ] Any dependent changes have been merged and published
- [ ] TypeScript types are properly defined (no `any`)
- [ ] Design tokens (Royal Plum, Electric Lime) are used correctly
- [ ] Bundle size impact is acceptable (check CI report)

## Performance Impact
<!-- Влияние на производительность -->

- Bundle size change: <!-- +/- XX KB -->
- Build time impact: <!-- +/- X seconds -->
- Runtime performance: <!-- Improved / No change / Degraded -->

## Security Considerations
<!-- Вопросы безопасности -->

- [ ] No sensitive data exposed in code
- [ ] No console.log with user data
- [ ] API endpoints properly authenticated
- [ ] Input validation implemented
- [ ] XSS prevention measures in place

## Deployment Notes
<!-- Важная информация для деплоя -->

- [ ] No database migrations required
- [ ] No environment variables changes
- [ ] No breaking API changes
- [ ] Backward compatible

## Reviewer Notes
<!-- Комментарии для ревьюеров -->

<!-- Укажите области, на которые ревьюерам стоит обратить особое внимание -->

---

**For Reviewers:**
- Focus on TypeScript types and React hooks dependencies
- Verify design system compliance (no shadows, 2px borders, Royal Plum + Electric Lime)
- Check bundle size impact in CI report
- Test Demo Mode functionality if applicable
