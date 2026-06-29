import { useState } from 'react';

interface Props {
  onSubmit: (category: string, comment: string) => void;
  onClose: () => void;
}

const CATEGORIES = ['incorrect', 'missing_source', 'incomplete', 'slow', 'other'];

export default function FeedbackModal({ onSubmit, onClose }: Props) {
  const [selectedCategory, setSelectedCategory] = useState('other');
  const [comment, setComment] = useState('');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <span className="modal-title">What went wrong?</span>
          <button className="btn-ghost" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="category-chips">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                className={`category-chip ${selectedCategory === cat ? 'selected' : ''}`}
                onClick={() => setSelectedCategory(cat)}
              >
                {cat.replace('_', ' ')}
              </button>
            ))}
          </div>
          <textarea
            placeholder="Additional comments (optional)..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <button
            className="btn btn-primary"
            style={{ marginTop: 16, width: '100%' }}
            onClick={() => onSubmit(selectedCategory, comment)}
          >
            Submit feedback
          </button>
        </div>
      </div>
    </div>
  );
}
