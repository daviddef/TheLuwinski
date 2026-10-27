/* THE MINI FLAGS ON THE RIBBON CARDS (27 October 2026; kit/docs/ribbon-flags.md). src/data/ribbon-flags.json holds each ribbon
   card's flags, made by tools/build-ribbon-flags.py with the kit's generator (never typed); this puts them on the cards as the page
   draws them, so story.json and family-lines.json stay as their own contracts know them. A card gets its flags only where the
   entry's position and name (or, for a living card, `living`) still match; one that does not gets none, and the kit's gate
   (check:ribbonflags, R7) then fails the build until the file is made again. */
import flagData from '../data/ribbon-flags.json';

const matches = (e, card) => (e.living ? !!(card.living || card.minor) : !card.living && !card.minor && e.name === card.name);

function put(cards, entries) {
  return (cards || []).map((card, i) => {
    const e = (entries || []).find((x) => x.card === i + 1);
    return e && matches(e, card) ? { ...card, flags: e.flags } : card;
  });
}

/* the story's book with its ribbon's cards flagged */
export function storyWithFlags(book) {
  if (!book || !book.ribbon) return book;
  return { ...book, ribbon: { ...book.ribbon, cards: put(book.ribbon.cards, flagData.story) } };
}

/* one family of family-lines.json with its cards flagged */
export function familyWithFlags(fam) {
  if (!fam || !fam.cards) return fam;
  return { ...fam, cards: put(fam.cards, (flagData.families || {})[fam.id]) };
}
