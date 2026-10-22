import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import SpotDifferenceRenderer from './SpotDifferenceRenderer.jsx';

const ANCHORS = Array.from({ length: 12 }, (_, index) => ({
  id: `a${index + 1}`,
  shape: index % 3 === 0 ? 'circle' : index % 3 === 1 ? 'rect' : 'star',
  x: 40 + (index % 4) * 90,
  y: 50 + Math.floor(index / 4) * 80,
  w: 30,
  h: 24,
  color: '#f87171',
  label: `مرساة ${index + 1}`,
}));

// عقد الخلفية: معرّف التحوّل هو نفسه معرّف المرساة، ومعرّف الفرق كذلك.
const MUTATIONS = [
  { id: 'a1', type: 'color', from: '#f87171', to: '#22d3ee' },
  { id: 'a2', type: 'missing' },
  { id: 'a3', type: 'scale', scale: 1.5 },
];

const DIFFERENCES = [
  { id: 'a1', x: 40, y: 50, r: 30, label: 'تغيّر لون العلم', mutation: 'color' },
  { id: 'a2', x: 130, y: 50, r: 30, label: 'اختفاء الكرة', mutation: 'missing' },
  { id: 'a3', x: 220, y: 50, r: 34, label: 'كبر الحجم', mutation: 'scale' },
];

const QUESTION = {
  id: 'backend-9',
  sceneId: 'towers',
  anchors: ANCHORS,
  mutations: MUTATIONS,
  differences: DIFFERENCES,
  question: 'طلع الفروقات الثلاثة',
};

function count(haystack, needle) {
  return haystack.split(needle).length - 1;
}

describe('SpotDifferenceRenderer', () => {
  it('renders the backend scene, eleven visible anchors and the missing one omitted', () => {
    const html = renderToStaticMarkup(<SpotDifferenceRenderer question={QUESTION} />);

    expect(html).toContain('كورنيش أبراج الكويت');
    expect(html).toContain('مولّد إجرائيًا');
    // الصورة (أ) ترسم المراسي الاثني عشر، والصورة (ب) ترسم أحد عشر لأن المتحوّل
    // بـ missing يُحذف فعليًا من اليمين فقط — أي 12 + 11 = 23 شكلًا.
    expect(count(html, 'data-anchor-id=')).toBe(23);
    expect(count(html, 'data-anchor-id="a2"')).toBe(1);
    expect(html).toContain('data-mutation="color"');
    expect(html).toContain('data-mutation="scale"');
  });

  it('turns each declared difference into exactly one interactive target', () => {
    const html = renderToStaticMarkup(<SpotDifferenceRenderer question={QUESTION} />);

    expect(count(html, 'role="button"')).toBe(3);
    expect(count(html, 'ابحث هنا')).toBe(3);
    expect(html).toContain('لقيته <span class="ltr">0</span> من <span class="ltr">3</span>');
  });

  it('reveals the Arabic labels of the three real differences after resolution', () => {
    const html = renderToStaticMarkup(<SpotDifferenceRenderer question={QUESTION} revealed />);

    for (const difference of DIFFERENCES) {
      expect(html).toContain(difference.label);
    }
    expect(html).toContain('لقيته <span class="ltr">3</span> من <span class="ltr">3</span>');
  });
});
