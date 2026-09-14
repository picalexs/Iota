import { useEffect, useMemo, useState } from "react";

export function useBulkSelection<TId extends string>(itemIds: readonly TId[]) {
  const [isEditing, setIsEditing] = useState(false);
  const [selectedIds, setSelectedIds] = useState<TId[]>([]);

  const visibleIdSet = useMemo(() => new Set(itemIds), [itemIds]);
  const selectedIdSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  useEffect(() => {
    setSelectedIds((current) => {
      const next = current.filter((id) => visibleIdSet.has(id));
      return next.length === current.length ? current : next;
    });
  }, [visibleIdSet]);

  const selectedCount = selectedIds.length;
  const allVisibleSelected = itemIds.length > 0 && itemIds.every((id) => selectedIdSet.has(id));
  const someVisibleSelected = !allVisibleSelected && itemIds.some((id) => selectedIdSet.has(id));

  function enterEditing() {
    setIsEditing(true);
  }

  function exitEditing() {
    setIsEditing(false);
    setSelectedIds([]);
  }

  function toggleEditing(next?: boolean) {
    const shouldEdit = next ?? !isEditing;
    if (shouldEdit) {
      setIsEditing(true);
      return;
    }
    exitEditing();
  }

  function toggleSelected(id: TId) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id],
    );
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  function selectAllVisible() {
    setSelectedIds([...itemIds]);
  }

  function setAllVisibleSelected(selected: boolean) {
    if (selected) {
      selectAllVisible();
      return;
    }
    clearSelection();
  }

  function replaceSelection(ids: readonly TId[]) {
    setSelectedIds(ids.filter((id) => visibleIdSet.has(id)));
  }

  return {
    isEditing,
    selectedIds,
    selectedIdSet,
    selectedCount,
    allVisibleSelected,
    someVisibleSelected,
    enterEditing,
    exitEditing,
    toggleEditing,
    toggleSelected,
    clearSelection,
    selectAllVisible,
    setAllVisibleSelected,
    replaceSelection,
  };
}
