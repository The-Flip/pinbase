import { getContext, setContext } from 'svelte';
import type { ModelEditSectionKey } from './model-edit-sections';

const KEY = Symbol('modelEditAction');

type EditActionFn = (key: ModelEditSectionKey) => (() => void) | undefined;

export function setModelEditActionContext(fn: EditActionFn): void {
	setContext(KEY, fn);
}

export function getModelEditActionContext(): EditActionFn {
	const fn = getContext<EditActionFn | undefined>(KEY);
	if (!fn) {
		throw new Error('modelEditAction context missing — must be rendered inside the model layout');
	}
	return fn;
}
