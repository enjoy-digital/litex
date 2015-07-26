#ifndef __PTHREAD_H
#define __PTHREAD_H

typedef int pthread_rwlock_t;

#define PTHREAD_RWLOCK_INITIALIZER 0

#ifdef __cplusplus
extern "C" {
#endif

inline int pthread_rwlock_rdlock(pthread_rwlock_t *rwlock)
  { return 0; }
inline int pthread_rwlock_tryrdlock(pthread_rwlock_t *rwlock)
  { return 0; }
inline int pthread_rwlock_wrlock(pthread_rwlock_t *rwlock)
  { return 0; }
inline int pthread_rwlock_trywrlock(pthread_rwlock_t *rwlock)
  { return 0; }
int pthread_rwlock_unlock(pthread_rwlock_t *rwlock)
  { return 0; }

#ifdef __cplusplus
}
#endif

#endif /* __PTHREAD_H */
