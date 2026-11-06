/**
 * Quita el front matter (`---` … `---` al principio) de una página Markdown: el de la documentación de util_bbdd 5.3.0
 * es JSON para herramientas e IA, y `marked` lo pintaría como una regla y un párrafo.
 */
export function stripFrontMatter(source: string): string {
  return source.replace(/^---\r?\n[\s\S]*?\r?\n---[ \t]*(?:\r?\n|$)/, '');
}
