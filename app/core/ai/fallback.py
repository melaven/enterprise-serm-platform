"""Детерминированные шаблоны на случай, когда LLM недоступна, вернула мусор или отзыв без текста.

Шаблоны намеренно нейтральны: без обещаний, сумм, сроков и признания вины. Все тексты проходят те же
проверки GeneratedDraft/DraftBatch, что и ответы модели (проверяется тестами).
"""

from __future__ import annotations

from typing import Final

from app.core.ai.schemas import (
    DraftBatch,
    DraftVariant,
    GeneratedDraft,
    Polarity,
    TenantContext,
)

_RU_PREFIX: Final = "Здравствуйте! "
_EN_PREFIX: Final = "Hello! "

_RU: Final[dict[tuple[bool, DraftVariant], str]] = {
    (True, DraftVariant.FORMAL): (
        "Благодарим вас за обратную связь. Мы приняли ваш отзыв в работу и проверим описанную ситуацию. "
        "Выводы будут учтены в работе {brand}."
    ),
    (True, DraftVariant.EMPATHETIC): (
        "Нам очень жаль, что ваше взаимодействие с {brand} оставило неприятные впечатления, и мы приносим "
        "извинения за доставленные неудобства. Ваше мнение важно для нас, мы постараемся разобраться."
    ),
    (True, DraftVariant.ACTION_ORIENTED): (
        "Мы хотим разобраться в ситуации и помочь. Опишите, пожалуйста, детали обращения {channel}: так мы "
        "быстрее найдём решение и свяжемся с вами."
    ),
    (False, DraftVariant.FORMAL): (
        "Благодарим вас за высокую оценку и обратную связь. Для {brand} важно, что вы выбрали нас."
    ),
    (False, DraftVariant.EMPATHETIC): (
        "Спасибо за тёплые слова, нам очень приятно это читать. Команда {brand} будет стараться и дальше "
        "оправдывать ваше доверие."
    ),
    (False, DraftVariant.ACTION_ORIENTED): (
        "Спасибо за отзыв! Будем рады видеть вас снова в {brand}, а если появятся пожелания, напишите нам "
        "{channel}."
    ),
}

_EN: Final[dict[tuple[bool, DraftVariant], str]] = {
    (True, DraftVariant.FORMAL): (
        "Thank you for your feedback. We have taken your review into work and will look into the situation "
        "you describe. The findings will be considered by {brand}."
    ),
    (True, DraftVariant.EMPATHETIC): (
        "We are sorry that your experience with {brand} was unpleasant and apologize for the inconvenience. "
        "Your opinion matters to us and we will try to understand what happened."
    ),
    (True, DraftVariant.ACTION_ORIENTED): (
        "We want to understand the situation and help. Please describe the details {channel} so that we can "
        "find a solution faster and get back to you."
    ),
    (False, DraftVariant.FORMAL): (
        "Thank you for your high rating and feedback. It matters to {brand} that you chose us."
    ),
    (False, DraftVariant.EMPATHETIC): (
        "Thank you for the kind words, it is a pleasure to read them. The {brand} team will keep working to "
        "earn your trust."
    ),
    (False, DraftVariant.ACTION_ORIENTED): (
        "Thank you for the review! We would be glad to see you at {brand} again, and if you have any "
        "wishes, please write to us {channel}."
    ),
}


def build_fallback_drafts(
    tenant: TenantContext, polarity: Polarity
) -> tuple[GeneratedDraft, ...]:
    """Три шаблонных варианта на языке тенанта (ru, иначе en). Mixed трактуется как негатив: безопаснее."""
    russian = tenant.language.lower().startswith("ru")
    templates = _RU if russian else _EN
    prefix = _RU_PREFIX if russian else _EN_PREFIX
    default_channel = (
        "в ответном сообщении" if russian else "in a reply to this message"
    )
    channel = (
        f"через {tenant.support_channel}"
        if (tenant.support_channel and russian)
        else (
            f"via {tenant.support_channel}"
            if tenant.support_channel
            else default_channel
        )
    )
    negative = polarity is not Polarity.POSITIVE
    signature = tenant.effective_signature

    drafts = tuple(
        GeneratedDraft(
            variant=variant,
            text=f"{prefix}{templates[(negative, variant)].format(brand=tenant.brand_name, channel=channel)} {signature}",
        )
        for variant in DraftVariant
    )
    DraftBatch(drafts=list(drafts))  # те же инварианты, что и для ответа модели
    return drafts
