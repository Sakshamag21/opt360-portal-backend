import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, X } from 'lucide-react';

/**
 * A searchable dropdown over a list of {name, code} options — shows names,
 * but the value it reports back (onChange) is the code, since that's what
 * the backend filters on (see docs/VIEW_OPERATORS_REDESIGN_PLAN.md §1).
 */
const NameCodeTypeahead = ({ label, options, value, onChange, placeholder = 'All' }) => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  const selected = useMemo(() => options.find(o => o.code === value) || null, [options, value]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    if (!query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter(o => o.name.toLowerCase().includes(q) || o.code.toLowerCase().includes(q));
  }, [options, query]);

  return (
    <div className="space-y-2 relative" ref={containerRef}>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="w-full flex items-center justify-between px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-left"
        >
          <span className={selected ? 'text-gray-900' : 'text-gray-400'}>
            {selected ? selected.name : placeholder}
          </span>
          <span className="flex items-center gap-1">
            {selected && (
              <X
                className="w-3.5 h-3.5 text-gray-400 hover:text-gray-600"
                onClick={(e) => { e.stopPropagation(); onChange(''); setQuery(''); }}
              />
            )}
            <ChevronDown className="w-4 h-4 text-gray-400" />
          </span>
        </button>

        {open && (
          <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-hidden flex flex-col">
            <input
              autoFocus
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Type to search..."
              className="px-3 py-2 text-sm border-b border-gray-200 focus:outline-none"
            />
            <div className="overflow-y-auto">
              <button
                type="button"
                onClick={() => { onChange(''); setQuery(''); setOpen(false); }}
                className="w-full text-left px-3 py-2 text-sm text-gray-500 hover:bg-gray-50"
              >
                {placeholder}
              </button>
              {filtered.length === 0 && (
                <div className="px-3 py-2 text-sm text-gray-400">No matches</div>
              )}
              {filtered.map(opt => (
                <button
                  type="button"
                  key={opt.code}
                  onClick={() => { onChange(opt.code); setQuery(''); setOpen(false); }}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-blue-50 ${opt.code === value ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'}`}
                >
                  {opt.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NameCodeTypeahead;
