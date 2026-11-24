import React, {
  useRef,
  type ButtonHTMLAttributes,
  type CSSProperties,
  type ReactNode
} from 'react';
import './SpecularButton.css';

export type SpecularButtonSize = 'sm' | 'md' | 'lg';
export type SpecularButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

export interface SpecularButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'type'> {
  children?: ReactNode;
  size?: SpecularButtonSize;
  variant?: SpecularButtonVariant;
  radius?: number;
  tint?: string;
  tintOpacity?: number;
  blur?: number;
  textColor?: string;
  lineColor?: string;
  baseColor?: string;
  intensity?: number;
  idleIntensity?: number;
  shineSize?: number;
  shineFade?: number;
  thickness?: number;
  glow?: number;
  speed?: number;
  followMouse?: boolean;
  proximity?: number;
  autoAnimate?: boolean;
  type?: 'button' | 'submit' | 'reset';
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  className?: string;
  style?: CSSProperties;
  disabled?: boolean;
}

export const SpecularButton = ({
  children = 'Get Started',
  size = 'md',
  variant,
  radius = 14,
  followMouse = true,
  disabled = false,
  onClick,
  className = '',
  type = 'button',
  style,
  // Accepted for backwards compatibility with existing call-sites
  tint: _tint,
  tintOpacity: _tintOpacity,
  blur: _blur,
  textColor,
  lineColor: _lineColor,
  baseColor: _baseColor,
  intensity: _intensity,
  idleIntensity: _idleIntensity,
  shineSize: _shineSize,
  shineFade: _shineFade,
  thickness: _thickness,
  glow: _glow,
  speed: _speed,
  proximity: _proximity,
  autoAnimate: _autoAnimate,
  ...rest
}: SpecularButtonProps) => {
  const buttonRef = useRef<HTMLButtonElement>(null);

  const handlePointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (!buttonRef.current || !followMouse || disabled) return;
    const rect = buttonRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    buttonRef.current.style.setProperty('--sb-shine-x', `${x}px`);
    buttonRef.current.style.setProperty('--sb-shine-y', `${y}px`);
    buttonRef.current.style.setProperty('--sb-shine-opacity', '1');
  };

  const handlePointerLeave = () => {
    if (!buttonRef.current) return;
    buttonRef.current.style.setProperty('--sb-shine-opacity', '0');
  };

  // Determine variant class: default to primary if not specified, unless caller provides styling
  const resolvedVariant = variant || 'primary';
  const variantClass = ` specular-button--${resolvedVariant}`;

  // Only apply textColor if caller explicitly specified a custom color that is not the dark default #f5f5f5
  // (unless the variant is primary where white text is desired).
  const inlineStyles: CSSProperties = {
    '--sb-radius': `${radius}px`,
    ...(textColor && resolvedVariant === 'primary' ? { color: textColor } : {}),
    ...style
  } as CSSProperties;

  return (
    <button
      ref={buttonRef}
      type={type}
      disabled={disabled}
      onClick={onClick}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      className={`specular-button specular-button--${size}${variantClass}${
        className ? ` ${className}` : ''
      }`}
      style={inlineStyles}
      {...rest}
    >
      <span className="specular-button__label">{children}</span>
    </button>
  );
};

export default SpecularButton;
